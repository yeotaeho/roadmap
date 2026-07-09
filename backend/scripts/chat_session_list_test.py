# 코치·상담 세션 목록·강제생성·자동제목 테스트 — 실 DB(생성 행 정리)
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

_pass = 0
_fail = 0


def check(name: str, cond: bool) -> None:
    global _pass, _fail
    if cond:
        _pass += 1
        print(f"PASS {name}")
    else:
        _fail += 1
        print(f"FAIL {name}")


async def _run_domain(label, repo_cls, msg_table, sess_table) -> None:
    from sqlalchemy import text

    from core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        uid = (await db.execute(text("SELECT id FROM users ORDER BY created_at DESC LIMIT 1"))).first()
        user_id = str(uid[0])

    async with AsyncSessionLocal() as db:
        repo = repo_cls(db)
        # 강제 생성 2회 → 서로 다른 세션.
        s1 = await repo.create_session(user_id)
        s2 = await repo.create_session(user_id)
        check(f"{label} create_new 서로 다름", s1 != s2)

        # 메시지 없으면 목록 제외.
        empty_list = await repo.list_sessions(user_id)
        check(f"{label} 빈 세션 목록 제외", all(x["id"] not in (s1, s2) for x in empty_list))

        # s1 에 메시지 + 제목.
        await repo.add_message(s1, "user", "데이터 분석가로 진로를 잡고 싶은데 무엇부터 할까요")
        await repo.set_title_if_empty(s1, "데이터 분석가로 진로를 잡고 싶은데 무엇부터 할까요"[:40])
        await repo.set_title_if_empty(s1, "덮어쓰면안됨")  # 멱등 — no-op.
        lst = await repo.list_sessions(user_id)
        found = next((x for x in lst if x["id"] == s1), None)
        check(f"{label} 메시지 세션 목록 포함", found is not None)
        check(f"{label} 제목 첫 메시지 고정", found and found["title"].startswith("데이터 분석가"))

        # 정리.
        await db.execute(text(f"DELETE FROM {msg_table} WHERE session_id IN (CAST(:a AS UUID), CAST(:b AS UUID))"), {"a": s1, "b": s2})
        await db.execute(text(f"DELETE FROM {sess_table} WHERE id IN (CAST(:a AS UUID), CAST(:b AS UUID))"), {"a": s1, "b": s2})
        await db.commit()


async def main() -> int:
    from domain.ai_coach.hub.repositories.coach_session_repository import CoachSessionRepository
    from domain.user_intelligence.hub.repositories.consult_session_repository import (
        ConsultSessionRepository,
    )

    await _run_domain("coach", CoachSessionRepository, "coach_messages", "coach_sessions")
    await _run_domain("consult", ConsultSessionRepository, "consult_messages", "consult_sessions")

    print(f"\nRESULT: PASS {_pass} / FAIL {_fail}")
    return 0 if _fail == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
