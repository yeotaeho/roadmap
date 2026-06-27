# KIAT → Pulse tech_demand 연결 실 DB 통합 검증

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from core.database import AsyncSessionLocal  # noqa: E402
from domain.market_insight.hub.repositories.pulse_repository import (  # noqa: E402
    PulseRepository,
)

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


async def main() -> int:
    async with AsyncSessionLocal() as s:
        repo = PulseRepository(s)

        # Task 2 — KIAT·KISTEP 미분류 행이 (raw_id, 본문) 으로 반환되는지.
        rows = await repo.fetch_unclassified_text_rows("raw_innovation_data", "v1", 3650, 5)
        check("innovation fetch list 반환", isinstance(rows, list))
        print(f"  innovation 미분류 fetch {len(rows)}건")
        if rows:
            rid, body = rows[0]
            check("fetch 본문 비어있지 않음", bool(body and body.strip()))
            print(f"  sample raw_id={rid} body_head={body[:80]!r}")

    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
