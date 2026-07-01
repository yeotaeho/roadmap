# 자기모델 ORM import·테이블 메타 검증(무DB)

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

from domain.user_intelligence.models.bases.user_self_model import UserSelfModel
from domain.user_intelligence.models.bases.user_self_model_evidence import UserSelfModelEvidence

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
    check("self_model 테이블명", UserSelfModel.__tablename__ == "user_self_model")
    cols = UserSelfModel.__table__.columns
    check("riasec nullable", cols["riasec"].nullable is True)
    check("source not null", cols["source"].nullable is False)
    ev = UserSelfModelEvidence.__table__
    check("evidence 테이블명", ev.name == "user_self_model_evidence")
    check("content not null", ev.columns["content"].nullable is False)
    check("is_sensitive not null", ev.columns["is_sensitive"].nullable is False)
    check("content_hash not null", ev.columns["content_hash"].nullable is False)
    check("dedup 유니크", any(c.name == "uq_self_model_evidence_dedup" for c in ev.constraints))
    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(run())
