# Gold(즉석) — 전통 vs 신흥 섹터 score 시계열 크로스오버 산출(결정론·DB 비의존 순수함수)

from __future__ import annotations

# 세대교체 내러티브 기준 6:6 고정 분류(섹터 강제 매핑 아님 — 산업 성격 기반 큐레이션).
LEGACY_SECTORS = (
    "semiconductor", "mobility", "food-agri", "logistics", "social-service", "beauty-fashion",
)
EMERGING_SECTORS = (
    "ai-data", "bio-health", "energy-climate", "fintech", "content-creator", "edutech",
)
LEGACY_LABEL = "전통 산업"
EMERGING_LABEL = "신흥 산업"


def assemble_crossover(rows: list[dict], legacy_label: str, emerging_label: str) -> dict:
    """버킷별 (legacy_value, emerging_value)에서 시계열·교차점을 조립한다.

    rows 는 bucket 오름차순. 두 값이 모두 있는 연속 버킷에서 (신흥−전통) 부호가
    전환되면 더 늦은 버킷에 is_crossover=True. 무네트워크 순수 함수.
    """
    series: list[dict] = []
    prev_diff: float | None = None
    for r in rows:
        lv = r.get("legacy_value")
        ev = r.get("emerging_value")
        is_crossover = False
        if lv is not None and ev is not None:
            diff = ev - lv
            if (
                prev_diff is not None
                and prev_diff != 0
                and diff != 0
                and (prev_diff > 0) != (diff > 0)
            ):
                is_crossover = True
            prev_diff = diff
        series.append(
            {
                "bucket": r["bucket"],
                "legacy_value": lv,
                "emerging_value": ev,
                "is_crossover": is_crossover,
            }
        )
    return {"legacy_label": legacy_label, "emerging_label": emerging_label, "series": series}
