# 시장 자금 기준선 수집 — 벤처투자종합포털(vcs.go.kr) 업종별 연도별 신규투자 총액 파싱·적재

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone

import httpx
from bs4 import BeautifulSoup
from sqlalchemy.ext.asyncio import AsyncSession

from domain.market_insight.hub.repositories.capital_flow_repository import (
    CapitalFlowRepository,
)

logger = logging.getLogger(__name__)

# robots 가 /web/portal/statistics/ 를 명시 허용. 공공저작물(자유이용).
_LIST_URL = "https://www.vcs.go.kr/web/portal/statistics/list"
_SOURCE_TYPE = "VCS_SECTOR_ANNUAL"
_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"

# vcs 업종 → 12섹터. 확실한 것만(강제 매핑 = 날조). 전기/기계/장비·화학/소재·유통/서비스·기타·합계는 무매핑.
_VCS_SECTOR_MAP: dict[str, str] = {
    "ICT서비스": "ai-data",
    "ICT제조": "semiconductor",
    "바이오/의료": "bio-health",
    "영상/공연/음반": "content-creator",
    "게임": "content-creator",
}
_TOTAL_LABELS = ("합계", "총계", "계")
_KST = timezone(timedelta(hours=9))
# 최신 연도가 '현재 KST 연도'이면서 직전 연도의 이 비율 미만일 때만 집계 진행 중(부분연도)으로 본다.
# 현재 연도 조건을 함께 걸어, 실제 40%+ 역성장한 '완결 과거 연도'를 부분연도로 오판·제외하는 것을 막는다.
_PARTIAL_RATIO = 0.6


def _to_won(cell: str) -> int | None:
    """'23,518'(억원) → 원 정수. 선두 숫자 그룹만 취해 '1,000~2,000'·주석 셀 오손을 막는다."""
    m = re.match(r"[\d,]+", (cell or "").strip())
    if not m:
        return None
    digits = m.group(0).replace(",", "")
    return int(digits) * 100_000_000 if digits else None


def parse_capital_table(html: str) -> list[dict]:
    """vcs statistics/list 의 업종별 투자실적 표 → 적재 레코드 목록.

    표 구조: 헤더 [구분, 2022..2026], 이후 각 행 [업종명, 연도별 억원...].
    """
    soup = BeautifulSoup(html, "html.parser")
    for table in soup.find_all("table"):
        head_cells = [th.get_text(strip=True) for th in table.find_all("th")]
        years = [int(c) for c in head_cells if re.fullmatch(r"20\d{2}", c)]
        if not years or not any("ICT" in c for c in head_cells):
            continue
        # 행별 (업종, {year: won})
        parsed: list[tuple[str, dict[int, int | None]]] = []
        for tr in table.find_all("tr"):
            cells = [c.get_text(strip=True) for c in tr.find_all(["th", "td"])]
            if len(cells) < 2 or not any(re.search(r"\d", c) for c in cells[1:]):
                continue
            label = cells[0]
            if label == "구분":
                continue
            vals = {y: _to_won(cells[i + 1]) for i, y in enumerate(years) if i + 1 < len(cells)}
            parsed.append((label, vals))
        if not parsed:
            continue
        # 부분연도 판정 — 합계 행의 최신 연도 vs 직전.
        totals = next((v for lbl, v in parsed if lbl in _TOTAL_LABELS), None)
        partial_years: set[int] = set()
        if totals and len(years) >= 2:
            last, prev = years[-1], years[-2]
            current_year = datetime.now(_KST).year
            if (
                last == current_year
                and totals.get(last)
                and totals.get(prev)
                and totals[last] < totals[prev] * _PARTIAL_RATIO
            ):
                partial_years.add(last)
        rows: list[dict] = []
        for label, vals in parsed:
            is_total = label in _TOTAL_LABELS
            slug = None if is_total else _VCS_SECTOR_MAP.get(label)
            for year, won in vals.items():
                is_partial = year in partial_years
                rows.append(
                    {
                        "vcs_category": label,
                        "sector_slug": slug,
                        "period_year": year,
                        "period_label": f"{year}(누적)" if is_partial else str(year),
                        "amount_krw": won,
                        "is_total": is_total,
                        "is_partial": is_partial,
                        "source_type": _SOURCE_TYPE,
                    }
                )
        return rows
    return []


class CapitalFlowRefineService:
    """vcs 업종별 신규투자 총액 수집·적재. 멱등."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = CapitalFlowRepository(session)

    async def refine_and_serve(self) -> dict:
        """vcs statistics/list 를 받아 파싱·적재. 반환 {rows, mapped, partial_years}."""
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                resp = await client.get(
                    _LIST_URL,
                    headers={"User-Agent": _UA, "Referer": "https://www.vcs.go.kr/web/portal/statistics/dashboard"},
                )
                resp.raise_for_status()
                html = resp.text
        except httpx.HTTPError as e:
            # 일시 장애는 잡 실패로 두지 않고 구조적 결과 반환(빈 파싱 분기와 동형).
            logger.warning("[capital_flow] vcs fetch 실패: %s", e)
            return {"rows": 0, "mapped": 0, "partial_years": [], "error": str(e)}
        rows = parse_capital_table(html)
        if not rows:
            logger.warning("[capital_flow] vcs 표 파싱 결과 없음 — 페이지 구조 변경 가능성.")
            return {"rows": 0, "mapped": 0, "partial_years": []}
        # taxonomy drift 조기 경보 — 매핑 업종 수가 바닥 밑이거나 미매핑 라벨이 새로 생기면 로그로 노출.
        unmapped = sorted({r["vcs_category"] for r in rows if not r["is_total"] and r["sector_slug"] is None})
        mapped_cats = {r["vcs_category"] for r in rows if r["sector_slug"]}
        if unmapped:
            logger.info("[capital_flow] 미매핑 업종=%s", unmapped)
        if len(mapped_cats) < 3:
            logger.warning("[capital_flow] 매핑 업종 %s개(<3) — vcs taxonomy 변경 의심", len(mapped_cats))
        await self.repo.upsert_many(rows)
        mapped = sum(1 for r in rows if r["sector_slug"] is not None)
        partial = sorted({r["period_year"] for r in rows if r["is_partial"]})
        logger.info("[capital_flow] rows=%s mapped=%s partial=%s", len(rows), mapped, partial)
        return {"rows": len(rows), "mapped": mapped, "partial_years": partial}
