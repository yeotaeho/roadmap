# 신규 사용자 ORM 메타데이터 등록 검증 — 테이블·컬럼 존재 확인

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

from core.database import Base  # noqa: E402
import alembic.env  # noqa: E402,F401  (모든 ORM을 메타데이터에 로드)

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
    tables = Base.metadata.tables
    check("user_profiles 등록", "user_profiles" in tables)
    check("user_preferences 등록", "user_preferences" in tables)
    persona_cols = set(tables["user_personas"].columns.keys())
    for c in ("certifications", "languages", "links", "projects"):
        check(f"user_personas.{c} 컬럼", c in persona_cols)
    prof_cols = set(tables["user_profiles"].columns.keys())
    for c in ("user_id", "birth_year", "gender", "region", "current_status", "education_level", "source"):
        check(f"user_profiles.{c} 컬럼", c in prof_cols)
    pref_cols = set(tables["user_preferences"].columns.keys())
    for c in ("user_id", "work_style", "company_size_pref", "work_type_pref", "work_values", "source"):
        check(f"user_preferences.{c} 컬럼", c in pref_cols)
    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(run())
