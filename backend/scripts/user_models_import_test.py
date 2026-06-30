# 신규 사용자 ORM 메타데이터 등록 검증 — 테이블·컬럼 존재 확인

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

from core.database import Base  # noqa: E402

# 모델 모듈을 직접 import 하여 Base.metadata 에 등록(alembic.env 우회 — 로컬 alembic 섀도잉 회피).
from domain.auth.models.bases.user_profile import UserProfile  # noqa: E402,F401
from domain.user_intelligence.models.bases.user_preference import UserPreference  # noqa: E402,F401
from domain.user_intelligence.models.bases.user_persona import UserPersona  # noqa: E402,F401


def run() -> int:
    passed = 0
    failed = 0

    def check(name: str, cond: bool, extra: str = "") -> None:
        nonlocal passed, failed
        if cond:
            passed += 1
            print(f"[PASS] {name}")
        else:
            failed += 1
            print(f"[FAIL] {name} {extra}")

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

    print(f"\n결과: PASS={passed} FAIL={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(run())
