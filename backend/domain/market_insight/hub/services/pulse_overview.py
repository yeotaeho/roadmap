# Pulse overview 결정론 조립 — raw 집계 dict → 대시보드 overview 응답(DB 비의존 순수함수)

from __future__ import annotations

# 주간지수(0~100)를 속도계 km/h(0~180)로 매핑하는 계수. 지수 100 → 180km/h.
_KMH_PER_INDEX = 1.8


def _gauge(latest: list[dict], daily_avgs: list[dict]) -> dict:
    scores = [r["score"] for r in latest]
    weekly_index = round(sum(scores) / len(scores)) if scores else None
    speed_kmh = round(weekly_index * _KMH_PER_INDEX) if weekly_index is not None else None

    day_delta_pct = None
    if len(daily_avgs) >= 2 and daily_avgs[1]["avg_score"]:
        d0, d1 = daily_avgs[0]["avg_score"], daily_avgs[1]["avg_score"]
        day_delta_pct = round((d0 - d1) / d1 * 100, 1)

    movers = [r for r in latest if r.get("momentum_pct") is not None]
    top_mover = None
    if movers:
        top = max(movers, key=lambda r: r["momentum_pct"])
        top_mover = {
            "sector_slug": top["sector_slug"],
            "sector_name": top["sector_name"],
            "momentum_pct": top["momentum_pct"],
        }
    return {
        "weekly_index": weekly_index,
        "speed_kmh": speed_kmh,
        "day_delta_pct": day_delta_pct,
        "top_mover": top_mover,
    }


def _heatmap(rows_latest: list[dict], weekly: list[dict]) -> dict:
    buckets = sorted({w["bucket"] for w in weekly})
    by_sector: dict[str, dict[str, int]] = {}
    for w in weekly:
        by_sector.setdefault(w["sector_slug"], {})[w["bucket"]] = w["score"]
    rows = [
        {
            "sector_slug": r["sector_slug"],
            "sector_name": r["sector_name"],
            "accent_color": r["accent_color"],
            "cells": [
                {"bucket": b, "score": by_sector.get(r["sector_slug"], {}).get(b)} for b in buckets
            ],
        }
        for r in rows_latest
        if r["sector_slug"] in by_sector
    ]
    return {"buckets": buckets, "rows": rows}


def _share(latest: list[dict]) -> list[dict]:
    total = sum(r["score"] for r in latest)
    if total <= 0:
        return []
    return [
        {
            "sector_slug": r["sector_slug"],
            "sector_name": r["sector_name"],
            "pct": round(r["score"] / total * 100, 1),
        }
        for r in latest
    ]


def assemble_overview(
    latest: list[dict],
    monthly: list[dict],
    weekly: list[dict],
    daily_avgs: list[dict],
) -> dict:
    """raw 집계 입력을 대시보드 overview 응답 형태로 조립한다(결정론·DB 비의존)."""
    rows_latest = sorted(latest, key=lambda r: r["score"], reverse=True)
    momentum_series = sorted(
        ({"bucket": m["bucket"], "value": int(m["value"])} for m in monthly),
        key=lambda p: p["bucket"],
    )
    return {
        "gauge": _gauge(rows_latest, daily_avgs),
        "momentum_series": momentum_series,
        "heatmap": _heatmap(rows_latest, weekly),
        "share": _share(rows_latest),
    }
