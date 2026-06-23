"""관세청 품목별 수출입실적(GW) OpenAPI로 HS코드별 월간 수출금액을 수집한다.

API 등록: https://www.data.go.kr/data/15101609/openapi.do (관세청_품목별 수출입실적)
API 키:   공공데이터포털(data.go.kr) ServiceKey (환경변수 CUSTOMS_SERVICE_KEY)
엔드포인트: http://apis.data.go.kr/1220000/Itemtrade/getItemtradeList
파라미터:  serviceKey, strtYymm(YYYYMM), endYymm(YYYYMM), hsSgn(HS부호)
응답필드:  hsCode(10자리 HS부호), statKor(품목명), expDlr(수출금액 USD),
          impDlr(수입금액 USD), expWgt/impWgt(중량 kg), balPayments(무역수지), year(기간)
          ※ 4자리 hsSgn 조회 시 10자리 세부행 + 총계행 1개 반환. 총계행은
            hsCode와 statKor이 모두 '-' → 합산 시 제외(중복 방지) 필수.
수집 주기: 월간 (전월 확정치가 익월 중순 공표 — 잠정치는 익월 초)
"""

from __future__ import annotations

import asyncio
import logging
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from typing import Any

import aiohttp

from domain.master.models.transfer.innovation_collect_dto import InnovationCollectDto

logger = logging.getLogger(__name__)

# 품목별 수출입실적(국가 무관 집계). 국가별이 필요하면 nitemtrade/getNitemtradeList 사용.
_API_URL = "http://apis.data.go.kr/1220000/Itemtrade/getItemtradeList"
_SOURCE_TYPE = "INNOVATION_CUSTOMS_EXPORT"

# (group_name, hs_codes, sector_label)
# HS 코드 앞 4자리 기준 (소호 수준)
_HS_CODE_GROUPS: list[tuple[str, list[str], str]] = [
    ("SEMICONDUCTOR",  ["8541", "8542"],         "반도체·집적회로"),
    ("DISPLAY",        ["8524", "9013"],          "디스플레이·광학부품"),
    ("AUTOMOTIVE",     ["8703", "8708"],          "자동차·부품"),
    ("MACHINERY",      ["8479", "8425", "8428"], "일반기계·하역기계"),
    ("CHEMICAL",       ["2901", "2902", "2909"], "화학·석유화학"),
    ("COSMETICS",      ["3304", "3305", "3307"], "화장품·K-뷰티"),
    ("FOOD_PROCESS",   ["0901", "2106", "2101"], "식품가공·음료"),
    ("STEEL_METAL",    ["7208", "7209", "7219"], "철강·비철금속"),
    ("SHIP_LOGISTICS", ["8901", "8902", "8716"], "선박·물류장비"),
    ("BATTERY",        ["8507", "8544"],          "이차전지·전선"),
]


def _target_yearmonth(ref: date, months_back: int = 2) -> str:
    """months_back개월 전 YYYYMM 반환.

    관세청 확정 통계는 익월 중순 공표되므로, 매월 1일 실행 시
    전월 데이터가 비어 있을 수 있어 기본 2개월 전을 조회한다.
    """
    cursor = ref.replace(day=1)
    for _ in range(months_back):
        cursor = (cursor - timedelta(days=1)).replace(day=1)
    return cursor.strftime("%Y%m")


def _parse_amount(value: Any) -> int:
    try:
        return int(float(str(value or "0").replace(",", "")))
    except (TypeError, ValueError):
        return 0


def _parse_xml_items(xml_text: str) -> tuple[list[dict[str, str]], str | None]:
    """관세청 GW 응답 XML을 파싱해 (item 리스트, resultCode)를 반환한다.

    정상 응답 구조: <response><header><resultCode>00</resultCode></header>
                    <body><items><item>...</item></items></body></response>
    """
    rows: list[dict[str, str]] = []
    result_code: str | None = None
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        logger.warning("[customs] XML 파싱 실패 — 응답 일부: %.200s", xml_text)
        return rows, result_code

    code_node = root.find(".//resultCode")
    if code_node is not None and code_node.text:
        result_code = code_node.text.strip()

    for item in root.findall(".//item"):
        row = {child.tag: (child.text or "").strip() for child in item}
        if row:
            rows.append(row)
    return rows, result_code


def _is_total_row(row: dict[str, str]) -> bool:
    """품목별 응답의 총계 행 여부. 합산 시 제외(중복 방지).

    관세청 응답의 총계행은 hsCode·statKor이 모두 '-'(또는 빈 값)로 온다.
    """
    name = (row.get("statKor") or "").strip()
    hs = (row.get("hsCode") or "").strip()
    return name in {"총계", "합계", "총 계", "-", ""} or hs in {"-", ""}


class CustomsExportCollector:
    """관세청 수출입무역통계 HS코드별 월간 수출금액 수집기.

    API 키 없으면 ValueError를 즉시 raise한다 (Ingest Service에서 HTTP 400 변환).
    """

    def __init__(self, service_key: str) -> None:
        if not service_key or not service_key.strip():
            raise ValueError("CUSTOMS_SERVICE_KEY가 설정되어 있지 않습니다.")
        self._key = service_key.strip()

    async def collect(
        self,
        *,
        yearmonth: str | None = None,
        hs_groups: list[tuple[str, list[str], str]] | None = None,
        sleep_seconds: float = 0.3,
    ) -> tuple[list[InnovationCollectDto], dict[str, int | str]]:
        """HS코드 그룹별 수출금액을 수집한다.

        yearmonth: YYYYMM 형식. 미입력 시 전월 자동 계산.
        """
        ym = yearmonth or _target_yearmonth(date.today())
        targets = hs_groups or _HS_CODE_GROUPS
        stats: dict[str, int | str] = {
            "yearmonth": ym,
            "groups_total": len(targets),
            "groups_ok": 0,
            "errors": 0,
            "fetched": 0,
        }

        rows: list[InnovationCollectDto] = []
        timeout = aiohttp.ClientTimeout(total=20)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            for i, (group_name, hs_codes, sector_label) in enumerate(targets):
                group_rows = await self._fetch_group(
                    session, group_name, hs_codes, sector_label, ym, stats
                )
                rows.extend(group_rows)
                if i < len(targets) - 1 and sleep_seconds > 0:
                    await asyncio.sleep(sleep_seconds)

        stats["fetched"] = len(rows)
        logger.info("[customs] 수출통계 수집 완료 %d건 (ym=%s)", len(rows), ym)
        return rows, stats

    async def _fetch_group(
        self,
        session: aiohttp.ClientSession,
        group_name: str,
        hs_codes: list[str],
        sector_label: str,
        ym: str,
        stats: dict[str, int | str],
    ) -> list[InnovationCollectDto]:
        group_rows: list[InnovationCollectDto] = []
        for hs_code in hs_codes:
            params = {
                "serviceKey": self._key,
                "strtYymm": ym,
                "endYymm": ym,
                "hsSgn": hs_code,
            }
            try:
                async with session.get(_API_URL, params=params) as resp:
                    resp.raise_for_status()
                    raw = await resp.text()

                items, result_code = _parse_xml_items(raw)
                if result_code and result_code not in {"00", "0"}:
                    logger.warning(
                        "[customs] HS%s resultCode=%s ym=%s — 응답 일부: %.150s",
                        hs_code, result_code, ym, raw,
                    )

                # 총계 행을 제외한 세부 품목 행만 합산 (중복 방지)
                detail_items = [it for it in items if not _is_total_row(it)]
                # 세부 행이 없으면(단일 4자리 집계 응답) 전체 행 사용
                summable = detail_items or items

                exp_dlr = sum(_parse_amount(it.get("expDlr")) for it in summable)
                imp_dlr = sum(_parse_amount(it.get("impDlr")) for it in summable)
                exp_wgt = sum(_parse_amount(it.get("expWgt")) for it in summable)

                source_url = f"{_API_URL}?hs={hs_code}&ym={ym}"
                group_rows.append(
                    InnovationCollectDto(
                        source_type=_SOURCE_TYPE,
                        source_url=source_url,
                        title=f"[{group_name}] HS{hs_code} 수출 {ym} ${exp_dlr:,}"[:500],
                        author_or_assignee=None,
                        abstract_text=None,
                        raw_metadata={
                            "hs_code": hs_code,
                            "group_name": group_name,
                            "sector_label": sector_label,
                            "yearmonth": ym,
                            "export_dollar": exp_dlr,   # 수출금액 (USD)
                            "import_dollar": imp_dlr,   # 수입금액 (USD)
                            "export_weight_kg": exp_wgt,
                            "trade_balance": exp_dlr - imp_dlr,
                            "raw_item_count": len(items),
                            "data_role": "EXPORT_FLOW_SIGNAL",
                        },
                        published_at=None,
                    )
                )
            except Exception:
                stats["errors"] = int(stats["errors"]) + 1
                logger.exception("[customs] HS%s 수집 실패 ym=%s", hs_code, ym)

        if group_rows:
            stats["groups_ok"] = int(stats["groups_ok"]) + 1
        return group_rows


__all__ = [
    "CustomsExportCollector",
    "_HS_CODE_GROUPS",
    "_SOURCE_TYPE",
]
