# 상담 세션 추출 지점 리포지토리 확장 Neon 테스트 — extracted_until·update·추출대상 조회

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

from sqlalchemy import text

from core.database import AsyncSessionLocal
from domain.user_intelligence.hub.repositories.consult_session_repository import ConsultSessionRepository

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
        raise SystemExit("users 비어있음")
    return str(r.id)


async def _cleanup(s, uid: str) -> None:
    await s.execute(text(
        "DELETE FROM consult_messages WHERE session_id IN "
        "(SELECT id FROM consult_sessions WHERE user_id = CAST(:u AS UUID))"), {"u": uid})
    await s.execute(text("DELETE FROM consult_sessions WHERE user_id = CAST(:u AS UUID)"), {"u": uid})
    await s.commit()


async def run() -> int:
    async with AsyncSessionLocal() as s:
        uid = await _uid(s)
        await _cleanup(s, uid)
        repo = ConsultSessionRepository(s)
        sid = await repo.create_session(uid)
        for i in range(8):
            await repo.add_message(sid, "user" if i % 2 == 0 else "assistant", f"m{i}")

        sess = await repo.get_session(sid)
        check("초기 extracted_until 0", sess["extracted_until"] == 0, str(sess))

        await repo.update_extracted(sid, 4)
        sess = await repo.get_session(sid)
        check("update_extracted 반영", sess["extracted_until"] == 4)

        # 8 메시지, extracted_until 4 → 신규 4. min_new=2 면 4>2 선택, min_new=5 면 미선택.
        sel2 = await repo.fetch_extractable_sessions(2, 10)
        check("추출대상 선택(min_new=2)", any(r["id"] == sid for r in sel2), str(sel2))
        sel5 = await repo.fetch_extractable_sessions(5, 10)
        check("미달 미선택(min_new=5)", all(r["id"] != sid for r in sel5), str(sel5))
        check("추출대상 user_id 동반", all("user_id" in r for r in sel2))

        # 정확히 min_new(=2 로 테스트) 개 신규 메시지 → 선택되어야 함(경계값, off-by-one 회귀).
        sid_boundary = await repo.create_session(uid)
        for i in range(2):
            await repo.add_message(sid_boundary, "user", f"b{i}")
        sel_boundary = await repo.fetch_extractable_sessions(2, 10)
        check("경계값(min_new=2) 선택됨", any(r["id"] == sid_boundary for r in sel_boundary), str(sel_boundary))

        await _cleanup(s, uid)
    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
