# Pulse overview 순수 조립 함수 무DB 검증 테스트

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from domain.market_insight.hub.services.pulse_overview import assemble_overview  # noqa: E402

PASS = 0
FAIL = 0


def check(name: str, cond: bool) -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"[PASS] {name}")
    else:
        FAIL += 1
        print(f"[FAIL] {name}")


def _latest() -> list[dict]:
    return [
        {"sector_slug": "ai-data", "sector_name": "AI·데이터", "accent_color": "#6366f1", "score": 90, "momentum_pct": 40.0},
        {"sector_slug": "fintech", "sector_name": "핀테크", "accent_color": "#10b981", "score": 60, "momentum_pct": 5.0},
    ]


def test_gauge_normal() -> None:
    out = assemble_overview(
        _latest(),
        monthly=[{"bucket": "2026-05", "value": 70}, {"bucket": "2026-06", "value": 75}],
        weekly=[],
        daily_avgs=[{"recorded_date": "2026-06-25", "avg_score": 75.0}, {"recorded_date": "2026-06-24", "avg_score": 60.0}],
    )
    g = out["gauge"]
    check("weekly_index = mean(90,60)=75", g["weekly_index"] == 75)
    check("speed_kmh = round(75*1.8)=135", g["speed_kmh"] == 135)
    check("day_delta_pct = (75-60)/60*100=25.0", g["day_delta_pct"] == 25.0)
    check("top_mover = ai-data(40.0)", g["top_mover"]["sector_slug"] == "ai-data")


def test_momentum_sorted() -> None:
    out = assemble_overview(
        _latest(),
        monthly=[{"bucket": "2026-06", "value": 75}, {"bucket": "2026-04", "value": 60}, {"bucket": "2026-05", "value": 70}],
        weekly=[],
        daily_avgs=[],
    )
    buckets = [p["bucket"] for p in out["momentum_series"]]
    check("momentum 오름차순 정렬", buckets == ["2026-04", "2026-05", "2026-06"])
    check("day_delta 날짜<2 → null", out["gauge"]["day_delta_pct"] is None)


def test_heatmap_pivot_and_null() -> None:
    out = assemble_overview(
        _latest(),
        monthly=[],
        weekly=[
            {"sector_slug": "ai-data", "bucket": "2026-W25", "score": 88},
            {"sector_slug": "ai-data", "bucket": "2026-W24", "score": 80},
            {"sector_slug": "fintech", "bucket": "2026-W25", "score": 55},
        ],
        daily_avgs=[],
    )
    hm = out["heatmap"]
    check("buckets 오름차순 distinct", hm["buckets"] == ["2026-W24", "2026-W25"])
    check("행 순서 = score 내림차순(ai-data 먼저)", hm["rows"][0]["sector_slug"] == "ai-data")
    fin_cells = {c["bucket"]: c["score"] for c in hm["rows"][1]["cells"]}
    check("결측 칸 null(fintech W24)", fin_cells["2026-W24"] is None)
    check("존재 칸 값(fintech W25=55)", fin_cells["2026-W25"] == 55)


def test_share_and_empty() -> None:
    out = assemble_overview(_latest(), monthly=[], weekly=[], daily_avgs=[])
    share = {s["sector_slug"]: s["pct"] for s in out["share"]}
    check("share ai-data = 90/150*100=60.0", share["ai-data"] == 60.0)
    check("share 합 100", round(sum(s["pct"] for s in out["share"]), 1) == 100.0)

    empty = assemble_overview([], monthly=[], weekly=[], daily_avgs=[])
    check("빈 latest → weekly_index null", empty["gauge"]["weekly_index"] is None)
    check("빈 latest → speed_kmh null", empty["gauge"]["speed_kmh"] is None)
    check("빈 latest → top_mover null", empty["gauge"]["top_mover"] is None)
    check("빈 latest → share []", empty["share"] == [])


def test_top_mover_none_momentum() -> None:
    latest = [{"sector_slug": "x", "sector_name": "X", "accent_color": "#000", "score": 50, "momentum_pct": None}]
    out = assemble_overview(latest, monthly=[], weekly=[], daily_avgs=[])
    check("모멘텀 전부 null → top_mover null", out["gauge"]["top_mover"] is None)


def test_heatmap_excludes_no_window_sector() -> None:
    """latest에는 있지만 weekly 윈도우에 없는 섹터는 히트맵 rows에서 제외되어야 한다."""
    out = assemble_overview(
        _latest(),
        monthly=[],
        weekly=[
            # ai-data만 weekly에 존재, fintech는 없음
            {"sector_slug": "ai-data", "bucket": "2026-W25", "score": 88},
        ],
        daily_avgs=[],
    )
    hm = out["heatmap"]
    slugs = [r["sector_slug"] for r in hm["rows"]]
    check("weekly 없는 섹터(fintech) rows 미포함", "fintech" not in slugs)
    check("weekly 있는 섹터(ai-data) rows 포함", "ai-data" in slugs)
    check("rows 길이 = 1", len(hm["rows"]) == 1)


def main() -> int:
    test_gauge_normal()
    test_momentum_sorted()
    test_heatmap_pivot_and_null()
    test_share_and_empty()
    test_top_mover_none_momentum()
    test_heatmap_excludes_no_window_sector()
    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
