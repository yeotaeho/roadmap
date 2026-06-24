# 모든 Bronze 수집 잡을 1회 실행하는 백필 — 스케줄러 잡 정의를 그대로 재사용

from __future__ import annotations

import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import scheduler as S  # noqa: E402


def _summary(result) -> str:
    if result is None:
        return "SKIP(키없음/조건)"
    if isinstance(result, dict):
        keys = ("source", "fetched", "inserted", "upserted", "not_inserted", "skipped_date")
        return ", ".join(f"{k}={result[k]}" for k in keys if k in result)
    return str(result)[:80]


async def main() -> None:
    # 중복 제거하며 일·주·월 잡 전체를 순서대로
    seen: set[str] = set()
    jobs: list[tuple[str, object]] = []
    for group in (S._DAILY_JOBS, S._WEEKLY_JOBS, S._MONTHLY_JOBS):
        for name, fn in group:
            if name in seen:
                continue
            seen.add(name)
            jobs.append((name, fn))

    print(f"== Bronze 백필 시작: {len(jobs)}개 잡 ==\n")
    ok = skip = err = 0
    for name, fn in jobs:
        t0 = time.monotonic()
        try:
            result = await fn()
            dt = time.monotonic() - t0
            if result is None:
                skip += 1
                print(f"[SKIP] {name:22s} ({dt:4.1f}s) — {_summary(result)}")
            else:
                ok += 1
                print(f"[ OK ] {name:22s} ({dt:4.1f}s) — {_summary(result)}")
        except Exception as e:
            dt = time.monotonic() - t0
            err += 1
            print(f"[ERR ] {name:22s} ({dt:4.1f}s) — {type(e).__name__}: {str(e)[:80]}")

    print(f"\n== 완료: OK {ok} / SKIP {skip} / ERR {err} (총 {len(jobs)}) ==")


if __name__ == "__main__":
    asyncio.run(main())
