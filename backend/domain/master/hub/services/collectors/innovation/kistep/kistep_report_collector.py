"""KISTEP 발간보고서 OpenAPI로 국가 미래 유망기술·R&D 정책 신호를 수집한다.

API 등록: 불필요 (KISTEP 자체 공개 엔드포인트 — serviceKey 파라미터 없음)
엔드포인트: https://www.kistep.re.kr/openApi24.es
파라미터:  startDate(YYYYMMDD), endDate(YYYYMMDD), boardNum(게시판 ID)
응답:      ⚠️ 정상 JSON이 아님. 본문 전체가 JSON 문자열로 한 번 인코딩돼 있고,
          디코드하면 바깥 래퍼(response/result/resultCode)만 JSON이며 result 배열
          내부는 중괄호·따옴표 없는 평면 `key=value, ` 나열이다(Java toString 직렬화).
          값에 쉼표·줄바꿈·한글이 섞이므로 '알려진 다음 필드명'을 경계로 슬라이스한다.
수집 주기: 주간 (최근 1년 롤링 윈도우, source_url로 멱등 처리)
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import date, timedelta
from typing import Any

import aiohttp

from domain.master.models.transfer.innovation_collect_dto import InnovationCollectDto

logger = logging.getLogger(__name__)

_API_URL = "https://www.kistep.re.kr/openApi24.es"
_SOURCE_TYPE = "INNOVATION_KISTEP_REPORT"
# 미래예측·유망기술 보고서 게시판. 다른 게시판 추가 시 이 리스트에 (board_num, label) append.
_DEFAULT_BOARDS: list[tuple[str, str]] = [
    ("831-006", "미래예측_유망기술"),
]

# result 배열 평면 본문에서 각 레코드가 갖는 필드 순서(고정). 값 경계 판별에 사용한다.
_KISTEP_FIELDS: tuple[str, ...] = (
    "resultCode", "resultMsg", "contentId", "policyType", "useYn",
    "brmCode", "brmTrans", "subject", "publishOrg", "contentsKor",
    "contentsPurps", "contentsCnclsn", "contentsRmk", "originUrl",
    "atchfileUrl", "atchfileNm", "viewCnt", "regDate", "deptMng",
)


def _find_result_list(parsed: Any) -> list[dict[str, Any]]:
    """정상 JSON 응답에서 result 배열을 추출한다 (래핑 구조 변화에 견고)."""
    if isinstance(parsed, list):
        return [item for item in parsed if isinstance(item, dict)]
    if isinstance(parsed, dict):
        result = parsed.get("result")
        if isinstance(result, list):
            return [item for item in result if isinstance(item, dict)]
        for child in parsed.values():
            found = _find_result_list(child)
            if found:
                return found
    return []


def _extract_result_array(body: str) -> str | None:
    """디코드된 본문에서 result 배열 내부(평면 key=value 나열)만 잘라낸다."""
    start_key = '"result":['
    si = body.find(start_key)
    if si == -1:
        return None
    vstart = si + len(start_key)
    # 평면 본문 종료 직후 래퍼가 `],"resultCode":...`로 이어진다.
    ei = body.find('],"resultCode"', vstart)
    if ei == -1:
        ei = body.rfind("]")
    if ei <= vstart:
        return None
    return body[vstart:ei]


def _parse_kistep_flat_records(arr: str) -> list[dict[str, Any]]:
    r"""`key=value, ` 평면 배열을 레코드 딕셔너리 리스트로 파싱한다.

    값에 쉼표·줄바꿈이 포함될 수 있어 단순 split이 불가능하므로,
    각 필드의 값은 '다음에 올 알려진 필드명'이 나타나는 위치까지로 한정한다.
    구분자는 레코드 내부 `, `(공백 有)와 레코드 경계 `,`(공백 無)가 섞여 있어
    `,\s*키=` 정규식으로 모두 허용한다. 마지막 필드(deptMng) 다음에는 다음 레코드의
    첫 필드(resultCode)가 이어진다.
    """
    records: list[dict[str, Any]] = []
    n = len(_KISTEP_FIELDS)
    length = len(arr)
    pos = 0
    while pos < length:
        rec: dict[str, Any] = {}
        for i, key in enumerate(_KISTEP_FIELDS):
            kpos = arr.find(f"{key}=", pos)
            if kpos == -1:
                break
            vstart = kpos + len(key) + 1
            next_key = _KISTEP_FIELDS[i + 1] if i + 1 < n else _KISTEP_FIELDS[0]
            m = re.compile(r",\s*" + re.escape(next_key) + r"=").search(arr, vstart)
            if m is None:
                value = arr[vstart:].strip()
                pos = length
            else:
                value = arr[vstart:m.start()].strip()
                pos = m.start()  # 다음 키 직전(구분자)부터 재탐색
            rec[key] = None if value == "null" else value
        if not rec:
            break
        records.append(rec)
    return records


def parse_kistep_payload(payload: str) -> list[dict[str, Any]]:
    text = payload.strip()
    if not text:
        return []
    # 1) 정상 JSON 우선 시도 (합성 테스트·향후 API 정상화 대비)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, (dict, list)):
        items = _find_result_list(parsed)
        if items:
            return items
    # 2) 이중 인코딩 + 평면 포맷: 바깥이 JSON 문자열이면 디코드 후 평면 파싱
    body = parsed if isinstance(parsed, str) else text
    arr = _extract_result_array(body)
    if arr is None:
        logger.warning("[kistep] result 배열을 찾지 못함 — 일부: %.150s", body)
        return []
    return _parse_kistep_flat_records(arr)


def kistep_item_to_dto(item: dict[str, Any], board_label: str) -> InnovationCollectDto | None:
    subject = str(item.get("subject") or "").strip()
    if not subject:
        return None
    content_id = str(item.get("contentId") or "").strip()
    origin_url = str(item.get("originUrl") or "").strip()
    # 멱등성 키: originUrl > contentId 합성 URL > 제목+발행일 합성 순으로 결정
    if origin_url:
        source_url = origin_url
    elif content_id:
        source_url = f"{_API_URL}?contentId={content_id}"
    else:
        source_url = f"{_API_URL}?subject={subject[:80]}&reg={item.get('regDate') or ''}"

    abstract_parts = [
        str(item.get("contentsPurps") or "").strip(),
        str(item.get("contentsCnclsn") or "").strip(),
        str(item.get("contentsKor") or "").strip(),
    ]
    abstract = " ".join(p for p in abstract_parts if p)[:2000]

    return InnovationCollectDto(
        source_type=_SOURCE_TYPE,
        source_url=source_url[:2000],
        title=subject[:500],
        author_or_assignee=str(item.get("publishOrg") or item.get("deptMng") or "")[:255] or None,
        abstract_text=abstract or None,
        raw_metadata={
            "content_id": content_id or None,
            "board_label": board_label,
            "publish_org": str(item.get("publishOrg") or "").strip() or None,
            "reg_date": str(item.get("regDate") or "").strip() or None,
            "attach_file_url": str(item.get("atchfileUrl") or "").strip() or None,
            "data_role": "FUTURE_TECH_SIGNAL",
        },
        published_at=None,
    )


class KistepReportCollector:
    """KISTEP 발간보고서 수집기 (인증키 불필요).

    source_url UNIQUE → ON CONFLICT DO NOTHING으로 멱등 처리.
    """

    def __init__(self, boards: list[tuple[str, str]] | None = None) -> None:
        self._boards = boards or _DEFAULT_BOARDS

    async def collect(
        self,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        sleep_seconds: float = 0.5,
    ) -> tuple[list[InnovationCollectDto], dict[str, int | str]]:
        end = end_date or date.today()
        start = start_date or (end - timedelta(days=365))
        start_str = start.strftime("%Y%m%d")
        end_str = end.strftime("%Y%m%d")

        stats: dict[str, int | str] = {
            "boards_total": len(self._boards),
            "boards_ok": 0,
            "errors": 0,
            "fetched": 0,
            "start_date": start_str,
            "end_date": end_str,
        }
        rows: list[InnovationCollectDto] = []
        timeout = aiohttp.ClientTimeout(total=25)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            for i, (board_num, board_label) in enumerate(self._boards):
                params = {
                    "startDate": start_str,
                    "endDate": end_str,
                    "boardNum": board_num,
                }
                try:
                    async with session.get(_API_URL, params=params) as resp:
                        resp.raise_for_status()
                        payload = await resp.text()
                    items = parse_kistep_payload(payload)
                    for item in items:
                        dto = kistep_item_to_dto(item, board_label)
                        if dto:
                            rows.append(dto)
                    stats["boards_ok"] = int(stats["boards_ok"]) + 1
                except Exception:
                    stats["errors"] = int(stats["errors"]) + 1
                    logger.exception("[kistep] board=%s 수집 실패", board_num)

                if i < len(self._boards) - 1 and sleep_seconds > 0:
                    await asyncio.sleep(sleep_seconds)

        stats["fetched"] = len(rows)
        logger.info("[kistep] 발간보고서 수집 완료 %d건", len(rows))
        return rows, stats


__all__ = [
    "KistepReportCollector",
    "parse_kistep_payload",
    "kistep_item_to_dto",
    "_DEFAULT_BOARDS",
    "_SOURCE_TYPE",
]
