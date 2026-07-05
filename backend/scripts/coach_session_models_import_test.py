# 코치 세션·메시지 ORM 임포트·스키마 단위 테스트(무DB)

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

from domain.ai_coach.models.bases.coach_message import CoachMessage
from domain.ai_coach.models.bases.coach_session import CoachSession

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


def run() -> int:
    check("세션 테이블명", CoachSession.__tablename__ == "coach_sessions")
    check("메시지 테이블명", CoachMessage.__tablename__ == "coach_messages")
    scols = {c.name for c in CoachSession.__table__.columns}
    check(
        "세션 컬럼",
        {"id", "user_id", "status", "started_at", "ended_at", "title", "context_summary", "summarized_until", "created_at"} <= scols,
    )
    check("추출 컬럼 없음(YAGNI)", "extracted_until" not in scols and "extracted_at" not in scols)
    mcols = {c.name for c in CoachMessage.__table__.columns}
    check("메시지 컬럼", {"id", "session_id", "role", "content", "created_at"} <= mcols)
    fk = list(CoachMessage.__table__.columns["session_id"].foreign_keys)[0]
    check("메시지 FK → coach_sessions", "coach_sessions" in str(fk.target_fullname))

    print(f"\n합계: PASS {PASS} / FAIL {FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(run())
