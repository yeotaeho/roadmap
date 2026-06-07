"""한국은행 ECOS OpenAPI 컬렉터 — 거시 자금 흐름(FDI·통화량·기준금리) 정형 시계열.

전략 (ECONOMIC_FLOW_IMPLEMENTATION_ROADMAP.md §4.1):
  - ECOS `StatisticSearch` REST 경로 호출 → 정형 시계열 row[] 수신.
  - 통계표/주기/항목 코드는 `_ECOS_TARGETS` 상수로 선언(★Probe로 검증 필요).
  - `source_url` 은 URL 이 없으므로 **합성 유니크 키** `ecos://{통계표}/{항목}/{TIME}`.
  - `investment_amount`: "유입 흐름"이 명확한 통계(FDI 등)만 매핑, 그 외(잔액·금리)는 None +
    값은 `raw_metadata.data_value`/`unit_name` 에 보존.

키: `.env` 의 `BOK_ECOS_API_KEY` (ecos.bok.or.kr/api 회원가입 시 발급).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import aiohttp

from domain.master.models.transfer.economic_collect_dto import EconomicCollectDto

logger = logging.getLogger(__name__)

BASE_URL = "https://ecos.bok.or.kr/api/StatisticSearch"
_KST = timezone(timedelta(hours=9))


@dataclass(frozen=True)
class EcosTarget:
    """단일 ECOS 통계표 수집 규칙.

    Attributes:
        stat_code: 통계표코드 (예: 기준금리 722Y001).
        cycle: 주기 — A(연)/Q(분기)/M(월)/D(일).
        item_code1: 항목코드1 (없으면 None — 통계표 전체).
        source_type: raw_economic_data.source_type.
        is_flow: True면 DATA_VALUE 를 investment_amount(원 단위 정수)로 매핑.
        label: 사람이 읽는 이름.
    """

    stat_code: str
    cycle: str
    item_code1: Optional[str]
    source_type: str
    is_flow: bool
    label: str


# 2026-06-07 Probe 결과로 확정된 코드.
#   기준금리: 722Y001/0101000 (월, 연%)
#   M2(광의통화 평잔 계절조정): 161Y005/BBHS00 (월, 십억원)
#   외국인직접투자 부채(국제수지 금융계정): 301Y013/BOPF12000000 (월, 백만달러)
_ECOS_TARGETS: tuple[EcosTarget, ...] = (
    EcosTarget("722Y001", "M", "0101000",      "BOK_ECOS_BASE_RATE",    False, "한국은행 기준금리"),
    EcosTarget("161Y005", "M", "BBHS00",       "BOK_ECOS_M2",           False, "광의통화(M2) 평잔 계절조정"),
    EcosTarget("301Y013", "M", "BOPF12000000", "BOK_ECOS_FDI_INBOUND",  False, "국제수지 직접투자(부채) 외국인→국내"),
)


class BokEcosCollector:
    """ECOS StatisticSearch 다중 통계표 수집기."""

    def __init__(self, service_key: str, targets: tuple[EcosTarget, ...] = _ECOS_TARGETS):
        if not service_key or not service_key.strip():
            raise ValueError(
                "BOK ECOS 인증키가 비어 있습니다. BOK_ECOS_API_KEY 를 설정하세요."
            )
        self._key = service_key.strip()
        self._targets = targets

    # -- 동기 래퍼 (스크립트/테스트 편의) ---------------------------------

    def collect_sync(self, *, start: str, end: str, max_rows: int = 10000) -> list[EconomicCollectDto]:
        import asyncio

        return asyncio.run(self.collect(start=start, end=end, max_rows=max_rows))

    # -- 메인 -------------------------------------------------------------

    async def collect(
        self, *, start: str, end: str, max_rows: int = 10000
    ) -> list[EconomicCollectDto]:
        """각 통계표를 [start, end] 기간으로 조회.

        Args:
            start/end: 주기에 맞는 일자 문자열 — 연 YYYY / 분기 YYYYQn / 월 YYYYMM / 일 YYYYMMDD.
            max_rows: 통계표당 요청 종료 건수(1회 최대).
        """
        out: list[EconomicCollectDto] = []
        timeout = aiohttp.ClientTimeout(total=45)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            for target in self._targets:
                try:
                    rows = await self._fetch_rows(session, target, start, end, max_rows)
                except Exception:
                    logger.exception(
                        "ECOS 통계표 수집 실패 stat=%s item=%s", target.stat_code, target.item_code1
                    )
                    continue
                for r in rows:
                    dto = self._to_dto(target, r)
                    if dto is not None:
                        out.append(dto)
        logger.info("ECOS collected dtos=%s", len(out))
        return out

    async def _fetch_rows(
        self,
        session: aiohttp.ClientSession,
        target: EcosTarget,
        start: str,
        end: str,
        max_rows: int,
    ) -> list[dict[str, Any]]:
        url = self._build_url(target, start, end, max_rows)
        try:
            async with session.get(url) as resp:
                body_text = await resp.text()
                if resp.status != 200:
                    logger.error(
                        "ECOS HTTP %s stat=%s body=%r",
                        resp.status,
                        target.stat_code,
                        body_text[:500],
                    )
                    raise RuntimeError(f"ECOS HTTP {resp.status}")
                import json

                data = json.loads(body_text)
        except aiohttp.ClientError as e:
            raise RuntimeError(f"ECOS 네트워크 오류: {e}") from e

        return self._parse_rows(data, target)

    def _build_url(self, target: EcosTarget, start: str, end: str, max_rows: int) -> str:
        """ECOS REST 경로 — 슬래시 구분 위치 인자."""
        parts = [
            BASE_URL,
            self._key,
            "json",
            "kr",
            "1",
            str(max_rows),
            target.stat_code,
            target.cycle,
            start,
            end,
        ]
        if target.item_code1:
            parts.append(target.item_code1)
        return "/".join(parts)

    @staticmethod
    def _parse_rows(data: dict[str, Any], target: EcosTarget) -> list[dict[str, Any]]:
        """ECOS 응답 → row 목록. 오류(RESULT) 또는 빈 응답이면 []."""
        if not isinstance(data, dict):
            return []
        # 오류 응답: {"RESULT": {"CODE": "INFO-200", "MESSAGE": "..."}}
        if "RESULT" in data and "StatisticSearch" not in data:
            result = data.get("RESULT") or {}
            logger.warning(
                "ECOS RESULT stat=%s code=%s msg=%s",
                target.stat_code,
                result.get("CODE"),
                result.get("MESSAGE"),
            )
            return []
        container = data.get("StatisticSearch")
        if not isinstance(container, dict):
            return []
        rows = container.get("row") or []
        return [r for r in rows if isinstance(r, dict)]

    @staticmethod
    def _to_int_amount(raw: Any) -> int | None:
        if raw is None:
            return None
        try:
            return int(round(float(str(raw).replace(",", "").strip())))
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _parse_time(time_str: str | None, cycle: str) -> datetime | None:
        if not time_str:
            return None
        t = str(time_str).strip()
        try:
            if cycle == "A":  # YYYY
                return datetime(int(t[:4]), 1, 1, tzinfo=_KST)
            if cycle == "M":  # YYYYMM
                return datetime(int(t[:4]), int(t[4:6]), 1, tzinfo=_KST)
            if cycle == "D":  # YYYYMMDD
                return datetime(int(t[:4]), int(t[4:6]), int(t[6:8]), tzinfo=_KST)
            if cycle == "Q":  # YYYYQn
                q = int(t[5:6]) if len(t) >= 6 else int(t[4:5])
                month = (q - 1) * 3 + 1
                return datetime(int(t[:4]), month, 1, tzinfo=_KST)
        except (ValueError, IndexError):
            return None
        return None

    def _to_dto(self, target: EcosTarget, row: dict[str, Any]) -> EconomicCollectDto | None:
        time_str = row.get("TIME")
        item_code = row.get("ITEM_CODE1") or (target.item_code1 or "")
        value = self._to_int_amount(row.get("DATA_VALUE"))
        stat_name = row.get("STAT_NAME") or target.label

        source_url = f"ecos://{target.stat_code}/{item_code}/{time_str or ''}"
        raw_title = f"{stat_name} {time_str or ''}".strip()[:500]

        raw_metadata: dict[str, Any] = {
            "stat_code": target.stat_code,
            "stat_name": stat_name,
            "item_code1": item_code or None,
            "item_name1": row.get("ITEM_NAME1"),
            "cycle": target.cycle,
            "time": time_str,
            "data_value": row.get("DATA_VALUE"),
            "unit_name": row.get("UNIT_NAME"),
            "data_role": "MACRO_FLOW" if target.is_flow else "MACRO_INDICATOR",
            "is_flow": target.is_flow,
            "collected_via": "bok-ecos-api",
            "original_item": row,
        }

        return EconomicCollectDto(
            source_type=target.source_type,
            source_url=source_url,
            raw_title=raw_title or target.label,
            investor_name="한국은행",
            target_company_or_fund=None,
            investment_amount=(value if target.is_flow else None),
            currency="KRW",
            raw_metadata=raw_metadata,
            published_at=self._parse_time(time_str, target.cycle),
        )


__all__ = ["BokEcosCollector", "EcosTarget"]
