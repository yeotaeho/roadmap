# 정제 파이프라인 직렬화(_REFINE_PIPELINE·_job_insight_refine_pipeline) 무네트워크 검증

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import core.scheduler as sched  # noqa: E402

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


_EXPECTED_ORDER = [
    "text_classify", "entity_extract", "investment_refine", "gap_refine",
    "tech_demand_gap", "gap_project", "causal_refine",
    "chance_refine", "chance_match", "document_embed", "user_embed",
    "pulse_refine", "briefing_refine", "sync_refine",
]


def test_pipeline_definition() -> None:
    names = [n for n, _ in sched._REFINE_PIPELINE]
    check("_REFINE_PIPELINE 스텝 순서 일치", names == _EXPECTED_ORDER)


def test_daily_jobs_composition() -> None:
    daily = [n for n, _ in sched._DAILY_JOBS]
    check("insight_refine 단일 잡 등록", daily.count("insight_refine") == 1)
    check(
        "개별 정제 스텝은 일일 잡에서 제거",
        all(step not in daily for step in _EXPECTED_ORDER),
    )


def test_pipeline_runs_in_order() -> None:
    recorded: list[str] = []

    async def _recorder(job_name, factory):
        recorded.append(job_name)

    original = sched._run_job
    sched._run_job = _recorder
    try:
        result = asyncio.run(sched._job_insight_refine_pipeline())
    finally:
        sched._run_job = original

    check("실행 순서 = 정의 순서", recorded == _EXPECTED_ORDER)
    check("steps 카운트 반환", result == {"steps": 14})


def main() -> int:
    test_pipeline_definition()
    test_daily_jobs_composition()
    test_pipeline_runs_in_order()
    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
