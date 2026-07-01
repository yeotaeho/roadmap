# 자기모델 리포지토리 Neon 라운드트립 — write/fetch·append dedup·민감 격리

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

from sqlalchemy import text

from core.database import AsyncSessionLocal
from domain.user_intelligence.hub.repositories.self_model_repository import (
    SelfModelRepository,
)

PASS = 0
FAIL = 0


def check(n: str, c: bool, e: str = "") -> None:
    global PASS, FAIL
    if c:
        PASS += 1
        print(f"[PASS] {n}")
    else:
        FAIL += 1
        print(f"[FAIL] {n} {e}")


async def _uid(s) -> str:
    r = (await s.execute(text("SELECT id FROM users ORDER BY created_at LIMIT 1"))).first()
    if r is None:
        raise SystemExit("users 테이블이 비어 있습니다.")
    return str(r.id)


async def _cleanup(s, uid: str) -> None:
    await s.execute(text("DELETE FROM user_self_model_evidence WHERE user_id = CAST(:u AS UUID)"), {"u": uid})
    await s.execute(text("DELETE FROM user_self_model WHERE user_id = CAST(:u AS UUID)"), {"u": uid})
    await s.commit()


async def run() -> int:
    async with AsyncSessionLocal() as s:
        uid = await _uid(s)
        await _cleanup(s, uid)
        repo = SelfModelRepository(s)

        await repo.write_self_model(
            uid, {"scores": {"I": 80}, "top_codes": ["I"]}, None, "탐구형", {"riasec": 0.7}, "coach_extraction"
        )
        m = await repo.fetch_self_model(uid)
        check("write/fetch riasec", bool(m) and m["riasec"]["top_codes"] == ["I"], str(m))
        check("source 반영", bool(m) and m["source"] == "coach_extraction")

        items = [
            {"dimension": "like", "polarity": "like", "content": "발표에서 에너지를 얻는다", "confidence": 0.8},
            {"dimension": "like", "polarity": "like", "content": "발표에서  에너지를 얻는다"},  # 정규화 시 동일 → dedup
            {"dimension": "constraint", "content": "장거리 통근 불가", "is_sensitive": True},
        ]
        n = await repo.append_evidence(uid, items, "coach_extraction")
        check("dedup 삽입 2건", n == 2, str(n))
        n2 = await repo.append_evidence(uid, items, "coach_extraction")
        check("재삽입 dedup 0건", n2 == 0, str(n2))

        non_sensitive = await repo.fetch_evidence(uid, include_sensitive=False)
        check("비민감 fetch 는 constraint 제외", all(e["dimension"] != "constraint" for e in non_sensitive), str(non_sensitive))
        allev = await repo.fetch_evidence(uid, include_sensitive=True)
        check("include_sensitive 는 constraint 포함", any(e["dimension"] == "constraint" for e in allev))

        await _cleanup(s, uid)
    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
