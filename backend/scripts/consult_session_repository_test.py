# 상담 세션 리포지토리 Neon 라운드트립 — 생성·메시지·히스토리 순서·요약·종료

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
        check("세션 생성 uuid", isinstance(sid, str) and len(sid) >= 32, sid)
        sess = await repo.get_session(sid)
        check("소유자 반영", sess and sess["user_id"] == uid, str(sess))
        check("초기 status active", sess and sess["status"] == "active")

        await repo.add_message(sid, "user", "안녕")
        await repo.add_message(sid, "assistant", "반가워요")
        await repo.add_message(sid, "user", "진로 고민이 있어")
        msgs = await repo.fetch_messages(sid)
        check("히스토리 3건 순서", [m["role"] for m in msgs] == ["user", "assistant", "user"], str(msgs))
        check("count 3", await repo.count_messages(sid) == 3)

        await repo.update_summary(sid, "사용자는 진로를 고민 중", 0)
        sess_after_summary = await repo.get_session(sid)
        check("요약 저장", sess_after_summary["context_summary"] == "사용자는 진로를 고민 중")
        check("summarized_until 초기 0", sess_after_summary["summarized_until"] == 0, str(sess_after_summary))

        await repo.update_summary(sid, "사용자는 진로를 고민 중(갱신)", 12)
        sess_after_update = await repo.get_session(sid)
        check("summarized_until 갱신", sess_after_update["summarized_until"] == 12, str(sess_after_update))

        check("최근 active 세션 = 생성분", await repo.get_latest_active_session(uid) == sid)

        await repo.end_session(sid)
        check("종료 status ended", (await repo.get_session(sid))["status"] == "ended")
        check("종료 후 active 없음", await repo.get_latest_active_session(uid) is None)

        await _cleanup(s, uid)
    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
