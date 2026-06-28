# 섹터×축 신호 밀도 진단 — Pulse min_history 게이트까지 남은 거리 측정

from __future__ import annotations

import asyncio
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

# Windows cp949 콘솔에서 한글·em dash 출력 깨짐 방지
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from domain.market_insight.hub.services.pulse_pipeline import (  # noqa: E402
    AxisSignal,
    compute_silver,
    fuse_signals,
)
from domain.market_insight.hub.services.text_sector_classify_service import (  # noqa: E402
    PROMPT_VERSION,
    SECTOR_SLUGS,
)

# 진단 대상 축 — pulse_repository.fetch_axis_signals 가 방출하는 7축.
AXES: tuple[str, ...] = (
    "innovation", "economic", "people", "market",
    "economic_text", "discourse", "tech_demand",
)

WINDOW_DAYS = 20
MIN_HISTORY = 5


def compute_density_report(
    axis_signals: list[AxisSignal],
    *,
    window_days: int = WINDOW_DAYS,
    min_history: int = MIN_HISTORY,
    as_of: date | None = None,
) -> tuple[list[dict], date | None]:
    """축 신호 목록에서 섹터별 밀도·게이트 상태 리포트를 산출한다(순수 함수·결정론).

    각 섹터에 대해 ① 실제 파이프라인(fuse→compute_silver) 결과의 최신 행이 게이트에
    걸려 회색(score 50·momentum 0)인지, ② 최근 window_days 일 안에 축별로 신호가
    찍힌 '서로 다른 날짜 수'(밀도)를 함께 보고한다. ②가 ①의 원인을 설명한다.

    as_of: 윈도우 기준일. None 이면 데이터의 최신 날짜를 사용한다.
    """
    if as_of is None:
        all_dates = [a.reference_date for a in axis_signals]
        as_of = max(all_dates) if all_dates else None
    cutoff = (as_of - timedelta(days=window_days)) if as_of is not None else None

    def _in_window(d: date) -> bool:
        return as_of is not None and cutoff < d <= as_of

    # 섹터×축: 신호(value>0)가 찍힌 서로 다른 날짜 집합 — 윈도우 내 / 전체.
    win: dict[str, dict[str, set]] = defaultdict(lambda: defaultdict(set))
    tot: dict[str, dict[str, set]] = defaultdict(lambda: defaultdict(set))
    for a in axis_signals:
        if a.value > 0:
            tot[a.sector_slug][a.axis].add(a.reference_date)
            if _in_window(a.reference_date):
                win[a.sector_slug][a.axis].add(a.reference_date)

    # 실제 게이트 판정 — 운영 파이프라인 그대로(fuse→compute_silver).
    silver = compute_silver(
        fuse_signals(axis_signals), window_days=window_days, min_history=min_history
    )
    # 윈도우 내 점수 목록 + 최신 행 — 회색 판정은 pulse_overview 와 동일하게
    # "윈도우 내 비-null 점수가 전부 50" 기준(min_history 게이트·평탄 신호 모두 포착).
    scores_win: dict[str, list[int]] = defaultdict(list)
    latest: dict[str, object] = {}
    for r in silver:
        if _in_window(r.reference_date):
            scores_win[r.sector_slug].append(r.normalized_score)
        cur = latest.get(r.sector_slug)
        if cur is None or r.reference_date > cur.reference_date:  # type: ignore[attr-defined]
            latest[r.sector_slug] = r

    slugs = sorted(set(tot) | set(SECTOR_SLUGS))
    report: list[dict] = []
    for slug in slugs:
        lr = latest.get(slug)
        win_scores = scores_win.get(slug, [])
        gray = (not win_scores) or all(s == 50 for s in win_scores)
        report.append({
            "sector": slug,
            "latest_date": (lr.reference_date if lr else None),  # type: ignore[attr-defined]
            "latest_score": (lr.normalized_score if lr else None),  # type: ignore[attr-defined]
            "latest_badge": (lr.status_badge if lr else None),  # type: ignore[attr-defined]
            "gray": gray,
            "axis_window": {ax: len(win[slug].get(ax, set())) for ax in AXES},
            "axis_total": {ax: len(tot[slug].get(ax, set())) for ax in AXES},
        })
    # 회색 섹터를 위로(우선순위), 그 안에서 슬러그순.
    report.sort(key=lambda r: (not r["gray"], r["sector"]))
    return report, as_of


def _print_report(report: list[dict], as_of: date | None) -> None:
    print("\n" + "#" * 78)
    print("# 섹터×축 신호 밀도 진단 — Pulse 게이트(min_history "
          f"{MIN_HISTORY}/{WINDOW_DAYS}일) 까지 거리")
    print(f"# 윈도우 기준일(as_of): {as_of}")
    print("#" * 78)
    head = f"  {'섹터':<16}{'상태':<8}{'score':>6}  " + "".join(f"{ax[:5]:>7}" for ax in AXES)
    print("\n" + head)
    print("  " + "-" * (len(head) - 2))
    for r in report:
        status = "회색" if r["gray"] else "활성"
        score = r["latest_score"] if r["latest_score"] is not None else "-"
        cells = "".join(f"{r['axis_window'][ax]:>7}" for ax in AXES)
        print(f"  {r['sector']:<16}{status:<8}{str(score):>6}  {cells}")
    print("\n  * 숫자 = 최근 윈도우 안에 신호가 찍힌 '서로 다른 날짜 수'(축별).")
    print(f"  * 게이트 통과엔 융합 신호가 윈도우 내 {MIN_HISTORY}일 이상 필요. 시장축은 일별이라 충족이 쉽다.")
    gray = [r["sector"] for r in report if r["gray"]]
    print(f"\n  회색 섹터 {len(gray)}개: {', '.join(gray) if gray else '(없음)'}\n")


async def main() -> None:
    from core.config.settings import get_settings
    from core.database import AsyncSessionLocal
    from domain.market_insight.hub.repositories.pulse_repository import PulseRepository

    settings = get_settings()
    async with AsyncSessionLocal() as session:
        repo = PulseRepository(session)
        axis = await repo.fetch_axis_signals(
            text_confidence_min=settings.llm_classify_confidence_min,
            text_prompt_version=PROMPT_VERSION,
        )
    report, as_of = compute_density_report(axis)
    _print_report(report, as_of)
    print("[완료]\n")


if __name__ == "__main__":
    asyncio.run(main())
