# 코치 세션·메시지 ORM import·메타 검증(무DB)

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

from domain.ai_coach.models.bases.coach_session import CoachSession
from domain.ai_coach.models.bases.coach_message import CoachMessage

PASS = 0
FAIL = 0


def check(name: str, cond: bool, extra: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"[PASS] {name}")
    else:
        FAIL += 1
        print(f"[FAIL] {name} {extra}")


def run() -> int:
    s = CoachSession.__table__
    check("sessions 테이블", s.name == "coach_sessions")
    check("status not null", s.columns["status"].nullable is False)
    check("context_summary nullable", s.columns["context_summary"].nullable is True)
    check("summarized_until not null", s.columns["summarized_until"].nullable is False)
    check("ended_at nullable", s.columns["ended_at"].nullable is True)
    m = CoachMessage.__table__
    check("messages 테이블", m.name == "coach_messages")
    check("role not null", m.columns["role"].nullable is False)
    check("content not null", m.columns["content"].nullable is False)
    check("session 인덱스", any(ix.name == "ix_coach_messages_session" for ix in m.indexes))
    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(run())
