# 선택적 사용자 데이터 개인화 — Phase 1(백엔드 데이터층) 구현 플랜

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 선택적(전부 nullable) 사용자 데이터 4차원 중 기본정보·성향·스펙을 저장·조회하는 테이블·API를 만든다(키워드는 기존 sync-profile 재사용, 임베딩 통합은 Phase 2).

**Architecture:** 기존 persona 수직(ORM→repository(text SQL)→service→router→인프로세스 엔드포인트 테스트)을 그대로 미러링. `user_profiles`(auth 도메인)·`user_preferences`(user_intelligence 도메인) 테이블 신설 + `user_personas` JSONB 4컬럼 확장. 모든 쓰기는 `source='user_form'`.

**Tech Stack:** FastAPI · SQLAlchemy 2.0(async) · Alembic · PostgreSQL(Neon, JSONB) · httpx ASGITransport 테스트.

## Global Constraints

- 새 소스 파일 첫 줄은 한 줄 한국어 주석으로 역할 명시(config 제외).
- 한국어 문장 종결은 `.` `?` `!` 만(`:` 금지).
- 신규 FK는 전부 `UUID(as_uuid=True)` → `users.id`, `ondelete="CASCADE"`.
- 모든 신규 사용자 필드는 nullable. `source`만 `NOT NULL DEFAULT 'user_form'`.
- 수동 DDL 금지 — 스키마 변경은 alembic 리비전으로만. 생성 파일 검토 필수.
- DB(Neon 단일) 쓰기·마이그레이션 적용은 **사용자 승인 후** 실행. uvicorn/테스트 기동은 `SCHEDULER_ENABLED=false`.
- 테스트는 기존 컨벤션(`scripts/*_test.py`, `check()` 기반 인프로세스 httpx) 따름 — pytest 프레임워크 아님.
- 커밋은 논리적 단위(테이블/수직)마다. 무관 변경(pycache 등) 묶지 않기.
- 작업 기록(audit_trail.md)은 커밋 후 별도 — 경로 승인 필요(이 플랜 범위 밖).

---

### Task 1: ORM 모델 — user_profiles · user_preferences + persona 4컬럼 확장

**Files:**
- Create: `domain/auth/models/bases/user_profile.py`
- Create: `domain/user_intelligence/models/bases/user_preference.py`
- Modify: `domain/user_intelligence/models/bases/user_persona.py` (4 컬럼 추가)
- Modify: `alembic/env.py:73` 부근 (신규 ORM 2종 import 등록)
- Test: `scripts/user_models_import_test.py`

**Interfaces:**
- Produces: ORM 클래스 `UserProfile`(테이블 `user_profiles`), `UserPreference`(테이블 `user_preferences`). `UserPersona`에 `certifications`/`languages`/`links`/`projects: Mapped[list | None]` 추가. 전부 `Base.metadata`에 등록되어 Task 2 마이그레이션·이후 repo가 의존.

- [ ] **Step 1: import 검증 테스트 작성**

`scripts/user_models_import_test.py`:

```python
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
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `python scripts/user_models_import_test.py`
Expected: FAIL — `ModuleNotFoundError: ... user_profile` (alembic.env 가 미존재 모듈 import) 또는 `KeyError: 'user_profiles'`.

- [ ] **Step 3: UserProfile ORM 작성**

`domain/auth/models/bases/user_profile.py`:

```python
# 사용자 기본정보(데모그래픽) ORM — 온보딩·프로필에서 선택 입력(전부 nullable, 임베딩 제외)

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, SmallInteger, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from core.database import Base


class UserProfile(Base):
    __tablename__ = "user_profiles"
    __table_args__ = {"comment": "사용자 기본정보(데모그래픽) — 선택 입력, 임베딩 직렬화 제외"}

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", name="fk_user_profile_user", ondelete="CASCADE"),
        primary_key=True,
    )
    birth_year: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(10), nullable=True)  # male|female|other
    region: Mapped[str | None] = mapped_column(String(50), nullable=True)
    current_status: Mapped[str | None] = mapped_column(String(20), nullable=True)  # student|job_seeking|employed|career_switch
    education_level: Mapped[str | None] = mapped_column(String(20), nullable=True)  # high_school|undergrad|bachelor|master|phd
    source: Mapped[str] = mapped_column(String(20), nullable=False, server_default="user_form")
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
```

- [ ] **Step 4: UserPreference ORM 작성**

`domain/user_intelligence/models/bases/user_preference.py`:

```python
# 사용자 성향·선호(disposition) ORM — 선택 입력, 임베딩 직렬화 포함(전부 nullable)

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from core.database import Base


class UserPreference(Base):
    __tablename__ = "user_preferences"
    __table_args__ = {"comment": "사용자 성향·선호 — 작업성향·기업규모·근무형태·일의가치(선택 입력)"}

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", name="fk_user_preference_user", ondelete="CASCADE"),
        primary_key=True,
    )
    work_style: Mapped[str | None] = mapped_column(String(20), nullable=True)  # stability|challenge|balanced
    company_size_pref: Mapped[str | None] = mapped_column(String(20), nullable=True)  # startup|sme|large|public
    work_type_pref: Mapped[str | None] = mapped_column(String(20), nullable=True)  # office|remote|hybrid
    work_values: Mapped[list | None] = mapped_column(JSONB, nullable=True)  # ["growth","work_life_balance",...]
    source: Mapped[str] = mapped_column(String(20), nullable=False, server_default="user_form")
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
```

- [ ] **Step 5: user_persona.py 에 4 컬럼 추가**

`domain/user_intelligence/models/bases/user_persona.py` 의 `summary` 컬럼 정의 바로 아래(라인 31 다음)에 추가:

```python
    # 스펙 심화(전부 nullable) — Phase 1 확장
    # [{name, issuer, year}]
    certifications: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # [{language, test, score}]
    languages: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # [{type: github|portfolio|blog, url}]
    links: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # [{title, description, role, period, tech_stack: [str]}]
    projects: Mapped[list | None] = mapped_column(JSONB, nullable=True)
```

(파일 상단 import 에 `JSONB` 는 이미 존재 — 확인만.)

- [ ] **Step 6: env.py 에 신규 ORM 등록**

`alembic/env.py` 의 `from domain.user_intelligence.models.bases.user_persona import UserPersona  # Persona` (라인 73) **바로 다음 줄**에 추가:

```python
from domain.auth.models.bases.user_profile import UserProfile  # 기본정보
from domain.user_intelligence.models.bases.user_preference import UserPreference  # 성향·선호
```

- [ ] **Step 7: 테스트 실행 → 통과 확인**

Run: `python scripts/user_models_import_test.py`
Expected: PASS — 모든 체크 PASS, FAIL=0.

- [ ] **Step 8: 커밋**

```bash
git add domain/auth/models/bases/user_profile.py domain/user_intelligence/models/bases/user_preference.py domain/user_intelligence/models/bases/user_persona.py alembic/env.py scripts/user_models_import_test.py
git commit -m "feat(user): user_profiles·user_preferences ORM + persona 스펙 4컬럼"
```

---

### Task 2: Alembic 마이그레이션 — 테이블 생성 + persona 컬럼 추가

**Files:**
- Create: `alembic/versions/a3f7c1e9d2b4_add_user_profile_preference_and_persona_specs.py`

**Interfaces:**
- Consumes: Task 1 의 ORM(테이블/컬럼 정의).
- Produces: Neon DB 에 `user_profiles`·`user_preferences` 테이블 + `user_personas` 4 컬럼. head 가 `a3f7c1e9d2b4` 로 전진. Task 3~5 의 엔드포인트 테스트가 이 스키마에 의존.

- [ ] **Step 1: 현재 head 재확인**

Run: `alembic heads`
Expected: `c8f1a2d3e4b5 (head)` 단일. (다르면 아래 `down_revision` 을 실제 head 로 교체.)

- [ ] **Step 2: 마이그레이션 파일 작성**

`alembic/versions/a3f7c1e9d2b4_add_user_profile_preference_and_persona_specs.py`:

```python
"""user_profiles·user_preferences 생성 + user_personas 스펙 4컬럼 추가."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "a3f7c1e9d2b4"
down_revision: Union[str, None] = "c8f1a2d3e4b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 기본정보(데모그래픽) — auth 소유, 전부 nullable ──
    op.create_table(
        "user_profiles",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("birth_year", sa.SmallInteger(), nullable=True),
        sa.Column("gender", sa.String(length=10), nullable=True),
        sa.Column("region", sa.String(length=50), nullable=True),
        sa.Column("current_status", sa.String(length=20), nullable=True),
        sa.Column("education_level", sa.String(length=20), nullable=True),
        sa.Column("source", sa.String(length=20), server_default="user_form", nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_user_profile_user", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id"),
        comment="사용자 기본정보(데모그래픽) — 선택 입력, 임베딩 직렬화 제외",
    )

    # ── 성향·선호 — user_intelligence 소유, 전부 nullable ──
    op.create_table(
        "user_preferences",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("work_style", sa.String(length=20), nullable=True),
        sa.Column("company_size_pref", sa.String(length=20), nullable=True),
        sa.Column("work_type_pref", sa.String(length=20), nullable=True),
        sa.Column("work_values", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("source", sa.String(length=20), server_default="user_form", nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_user_preference_user", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id"),
        comment="사용자 성향·선호 — 작업성향·기업규모·근무형태·일의가치(선택 입력)",
    )

    # ── persona 스펙 심화 4컬럼(nullable) ──
    op.add_column("user_personas", sa.Column("certifications", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("user_personas", sa.Column("languages", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("user_personas", sa.Column("links", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("user_personas", sa.Column("projects", postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column("user_personas", "projects")
    op.drop_column("user_personas", "links")
    op.drop_column("user_personas", "languages")
    op.drop_column("user_personas", "certifications")
    op.drop_table("user_preferences")
    op.drop_table("user_profiles")
```

- [ ] **Step 3: 마이그레이션 정합 검증(오프라인 SQL 생성)**

Run: `alembic upgrade c8f1a2d3e4b5:a3f7c1e9d2b4 --sql`
Expected: `CREATE TABLE user_profiles`, `CREATE TABLE user_preferences`, `ALTER TABLE user_personas ADD COLUMN ...` SQL 이 에러 없이 출력. (DB 미적용 — SQL 텍스트만.)

- [ ] **Step 4: 사용자 승인 후 Neon 적용**

> **GATE:** 실제 DB 적용 전 사용자에게 승인을 요청한다. 승인 전 실행 금지.

Run(승인 후): `alembic upgrade head`
Expected: `Running upgrade c8f1a2d3e4b5 -> a3f7c1e9d2b4`. 이후 `alembic current` → `a3f7c1e9d2b4 (head)`.

- [ ] **Step 5: 커밋**

```bash
git add alembic/versions/a3f7c1e9d2b4_add_user_profile_preference_and_persona_specs.py
git commit -m "feat(user): user_profiles·user_preferences·persona-specs 마이그레이션"
```

---

### Task 3: user_profiles 수직 — repository·service·라우터·엔드포인트 테스트

**Files:**
- Create: `domain/auth/hub/repositories/profile_repository.py`
- Create: `domain/auth/hub/services/profile_service.py`
- Modify: `api/v1/user/user_routor.py` (DTO + `GET/PUT /profile` 추가)
- Test: `scripts/profile_endpoint_test.py`

**Interfaces:**
- Consumes: Task 2 의 `user_profiles` 테이블. 기존 `BaseRepository`(`self.session`), 기존 `get_current_user_id`(user_routor 내), `JWTService`.
- Produces: `ProfileService(db).get_profile(uid) -> dict`, `.upsert_profile(uid, birth_year, gender, region, current_status, education_level) -> dict`. HTTP `GET/PUT /api/user/profile`.

- [ ] **Step 1: 엔드포인트 테스트 작성**

`scripts/profile_endpoint_test.py`:

```python
# 기본정보 엔드포인트 인프로세스 통합 테스트 — GET/PUT 라운드트립

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

import httpx  # noqa: E402
from sqlalchemy import text  # noqa: E402

from core.database import AsyncSessionLocal  # noqa: E402
from domain.auth.hub.security.services.jwt import JWTService  # noqa: E402

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


async def _resolve_user() -> str:
    async with AsyncSessionLocal() as s:
        r = (await s.execute(text("SELECT id FROM users ORDER BY created_at LIMIT 1"))).first()
        if r is None:
            raise SystemExit("users 테이블이 비어 있습니다.")
        return str(r.id)


async def run() -> int:
    from main import app

    uid = await _resolve_user()
    token = JWTService().generate_token(uid, provider="test", email="seed@test.local")
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "birthYear": 1999,
        "gender": "male",
        "region": "서울",
        "currentStatus": "job_seeking",
        "educationLevel": "bachelor",
    }

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/api/user/profile", headers=headers)
        check("GET 200", r.status_code == 200, str(r.status_code))
        check("GET success", r.json().get("success") is True)

        r = await client.put("/api/user/profile", headers=headers, json=payload)
        check("PUT 200", r.status_code == 200, str(r.status_code))
        saved = r.json().get("profile", {})
        check("PUT source=user_form", saved.get("source") == "user_form", str(saved.get("source")))

        r = await client.get("/api/user/profile", headers=headers)
        p = r.json().get("profile", {})
        check("birthYear 반영", p.get("birthYear") == 1999, str(p.get("birthYear")))
        check("region 반영", p.get("region") == "서울")
        check("currentStatus 반영", p.get("currentStatus") == "job_seeking")

        # 부분 입력(전부 nullable) — gender 만 None 으로 덮어쓰기 가능
        r = await client.put(
            "/api/user/profile", headers=headers,
            json={"birthYear": 1999, "region": "서울", "currentStatus": "job_seeking", "educationLevel": "bachelor"},
        )
        p = (await client.get("/api/user/profile", headers=headers)).json().get("profile", {})
        check("gender null 허용", p.get("gender") is None, str(p.get("gender")))

        r = await client.get("/api/user/profile")
        check("무토큰 401", r.status_code == 401, str(r.status_code))

    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `python scripts/profile_endpoint_test.py`
Expected: FAIL — `GET 200` 이 404(라우트 없음).

- [ ] **Step 3: ProfileRepository 작성**

`domain/auth/hub/repositories/profile_repository.py`:

```python
# 기본정보 리포지토리 — user_profiles 조회·upsert(데모그래픽, 선택 입력)

from __future__ import annotations

from sqlalchemy import text

from domain.auth.hub.repositories.base_repository import BaseRepository

_FETCH = text(
    """
    SELECT birth_year, gender, region, current_status, education_level, source
    FROM user_profiles
    WHERE user_id = CAST(:uid AS UUID)
    """
)

_UPSERT = text(
    """
    INSERT INTO user_profiles
        (user_id, birth_year, gender, region, current_status, education_level, source, updated_at)
    VALUES (CAST(:uid AS UUID), :birth_year, :gender, :region, :current_status, :education_level, :source, now())
    ON CONFLICT (user_id) DO UPDATE SET
        birth_year = EXCLUDED.birth_year,
        gender = EXCLUDED.gender,
        region = EXCLUDED.region,
        current_status = EXCLUDED.current_status,
        education_level = EXCLUDED.education_level,
        source = EXCLUDED.source,
        updated_at = now()
    """
)


class ProfileRepository(BaseRepository):
    async def fetch_profile(self, user_id: str) -> dict | None:
        r = (await self.session.execute(_FETCH, {"uid": user_id})).first()
        if r is None:
            return None
        return {
            "birth_year": r.birth_year,
            "gender": r.gender,
            "region": r.region,
            "current_status": r.current_status,
            "education_level": r.education_level,
            "source": r.source,
        }

    async def upsert_profile(
        self,
        user_id: str,
        birth_year: int | None,
        gender: str | None,
        region: str | None,
        current_status: str | None,
        education_level: str | None,
        source: str,
    ) -> None:
        await self.session.execute(
            _UPSERT,
            {
                "uid": user_id,
                "birth_year": birth_year,
                "gender": gender,
                "region": region,
                "current_status": current_status,
                "education_level": education_level,
                "source": source,
            },
        )
        await self.session.commit()
```

- [ ] **Step 4: ProfileService 작성**

`domain/auth/hub/services/profile_service.py`:

```python
# 기본정보 서비스 — 데모그래픽 선택 입력을 user_profiles 에 저장·조회

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from domain.auth.hub.repositories.profile_repository import ProfileRepository

# 폼 입력 출처 — coach 추출(미래) 과 구분.
SOURCE_USER_FORM = "user_form"


class ProfileService:
    def __init__(self, db: AsyncSession):
        self.repo = ProfileRepository(db)

    async def get_profile(self, user_id: str) -> dict:
        """없으면 전부 null 기본값(폼 초기 렌더용)."""
        profile = await self.repo.fetch_profile(user_id)
        if profile is None:
            return {
                "birthYear": None,
                "gender": None,
                "region": None,
                "currentStatus": None,
                "educationLevel": None,
                "source": None,
            }
        return {
            "birthYear": profile["birth_year"],
            "gender": profile["gender"],
            "region": profile["region"],
            "currentStatus": profile["current_status"],
            "educationLevel": profile["education_level"],
            "source": profile["source"],
        }

    async def upsert_profile(
        self,
        user_id: str,
        birth_year: int | None,
        gender: str | None,
        region: str | None,
        current_status: str | None,
        education_level: str | None,
    ) -> dict:
        await self.repo.upsert_profile(
            user_id,
            birth_year=birth_year,
            gender=gender,
            region=region,
            current_status=current_status,
            education_level=education_level,
            source=SOURCE_USER_FORM,
        )
        return {
            "birthYear": birth_year,
            "gender": gender,
            "region": region,
            "currentStatus": current_status,
            "educationLevel": education_level,
            "source": SOURCE_USER_FORM,
        }
```

- [ ] **Step 5: user_routor.py 에 DTO + 엔드포인트 추가**

`api/v1/user/user_routor.py` 상단 import 에 추가:

```python
from domain.auth.hub.services.profile_service import ProfileService
```

`SyncProfileUpsertRequest` 클래스 정의 다음(라인 21 부근)에 DTO 추가:

```python
class ProfileUpsertRequest(BaseModel):
    birthYear: Optional[int] = None
    gender: Optional[str] = None
    region: Optional[str] = None
    currentStatus: Optional[str] = None
    educationLevel: Optional[str] = None
```

파일 맨 끝(라인 131 다음)에 엔드포인트 추가:

```python
@router.get("/profile")
async def get_basic_profile(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """현재 사용자 기본정보 — 없으면 전부 null 기본값."""
    try:
        profile = await ProfileService(db).get_profile(user_id)
        return {"success": True, "profile": profile}
    except Exception as e:
        logger.error(f"기본정보 조회 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"기본정보 조회 실패: {str(e)}")


@router.put("/profile")
async def upsert_basic_profile(
    request: ProfileUpsertRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """기본정보 upsert — 폼 저장(전부 선택)."""
    try:
        profile = await ProfileService(db).upsert_profile(
            user_id,
            birth_year=request.birthYear,
            gender=request.gender,
            region=request.region,
            current_status=request.currentStatus,
            education_level=request.educationLevel,
        )
        return {"success": True, "profile": profile}
    except Exception as e:
        logger.error(f"기본정보 저장 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"기본정보 저장 실패: {str(e)}")
```

- [ ] **Step 6: 테스트 실행 → 통과 확인**

Run: `python scripts/profile_endpoint_test.py`
Expected: PASS — 전 체크 PASS, FAIL=0. (Task 2 마이그레이션 적용 전제.)

- [ ] **Step 7: 커밋**

```bash
git add domain/auth/hub/repositories/profile_repository.py domain/auth/hub/services/profile_service.py api/v1/user/user_routor.py scripts/profile_endpoint_test.py
git commit -m "feat(user): 기본정보 GET/PUT /api/user/profile 수직"
```

---

### Task 4: user_preferences 수직 — repository·service·신규 라우터·엔드포인트 테스트

**Files:**
- Create: `domain/user_intelligence/hub/repositories/preference_repository.py`
- Create: `domain/user_intelligence/hub/services/preference_service.py`
- Create: `api/v1/preferences/__init__.py`
- Create: `api/v1/preferences/preferences_routor.py`
- Modify: `main.py` (라우터 import + 등록)
- Test: `scripts/preferences_endpoint_test.py`

**Interfaces:**
- Consumes: Task 2 의 `user_preferences` 테이블. 기존 `BaseRepository`, `get_authenticated_user_id`(core.api_guards), `get_db`.
- Produces: `PreferenceService(db).get_preferences(uid) -> dict`, `.upsert_preferences(uid, work_style, company_size_pref, work_type_pref, work_values) -> dict`. HTTP `GET/PUT /api/preferences`.

- [ ] **Step 1: 엔드포인트 테스트 작성**

`scripts/preferences_endpoint_test.py`:

```python
# 성향·선호 엔드포인트 인프로세스 통합 테스트 — GET/PUT 라운드트립

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

import httpx  # noqa: E402
from sqlalchemy import text  # noqa: E402

from core.database import AsyncSessionLocal  # noqa: E402
from domain.auth.hub.security.services.jwt import JWTService  # noqa: E402

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


async def _resolve_user() -> str:
    async with AsyncSessionLocal() as s:
        r = (await s.execute(text("SELECT id FROM users ORDER BY created_at LIMIT 1"))).first()
        if r is None:
            raise SystemExit("users 테이블이 비어 있습니다.")
        return str(r.id)


async def run() -> int:
    from main import app

    uid = await _resolve_user()
    token = JWTService().generate_token(uid, provider="test", email="seed@test.local")
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "workStyle": "challenge",
        "companySizePref": "startup",
        "workTypePref": "hybrid",
        "workValues": ["growth", "autonomy"],
    }

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/api/preferences", headers=headers)
        check("GET 200", r.status_code == 200, str(r.status_code))
        check("GET success", r.json().get("success") is True)

        r = await client.put("/api/preferences", headers=headers, json=payload)
        check("PUT 200", r.status_code == 200, str(r.status_code))
        saved = r.json().get("preferences", {})
        check("PUT source=user_form", saved.get("source") == "user_form", str(saved.get("source")))

        r = await client.get("/api/preferences", headers=headers)
        p = r.json().get("preferences", {})
        check("workStyle 반영", p.get("workStyle") == "challenge")
        check("workValues 2개", len(p.get("workValues") or []) == 2, str(p.get("workValues")))
        check("companySizePref 반영", p.get("companySizePref") == "startup")

        r = await client.get("/api/preferences")
        check("무토큰 401", r.status_code == 401, str(r.status_code))

    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `python scripts/preferences_endpoint_test.py`
Expected: FAIL — `GET 200` 이 404.

- [ ] **Step 3: PreferenceRepository 작성**

`domain/user_intelligence/hub/repositories/preference_repository.py`:

```python
# 성향·선호 리포지토리 — user_preferences 조회·upsert(disposition)

from __future__ import annotations

import json

from sqlalchemy import text

from domain.auth.hub.repositories.base_repository import BaseRepository

_FETCH = text(
    """
    SELECT work_style, company_size_pref, work_type_pref, work_values, source
    FROM user_preferences
    WHERE user_id = CAST(:uid AS UUID)
    """
)

_UPSERT = text(
    """
    INSERT INTO user_preferences
        (user_id, work_style, company_size_pref, work_type_pref, work_values, source, updated_at)
    VALUES (CAST(:uid AS UUID), :work_style, :company_size_pref, :work_type_pref,
            CAST(:work_values AS JSONB), :source, now())
    ON CONFLICT (user_id) DO UPDATE SET
        work_style = EXCLUDED.work_style,
        company_size_pref = EXCLUDED.company_size_pref,
        work_type_pref = EXCLUDED.work_type_pref,
        work_values = EXCLUDED.work_values,
        source = EXCLUDED.source,
        updated_at = now()
    """
)


class PreferenceRepository(BaseRepository):
    async def fetch_preferences(self, user_id: str) -> dict | None:
        r = (await self.session.execute(_FETCH, {"uid": user_id})).first()
        if r is None:
            return None
        return {
            "work_style": r.work_style,
            "company_size_pref": r.company_size_pref,
            "work_type_pref": r.work_type_pref,
            "work_values": r.work_values or [],
            "source": r.source,
        }

    async def upsert_preferences(
        self,
        user_id: str,
        work_style: str | None,
        company_size_pref: str | None,
        work_type_pref: str | None,
        work_values: list,
        source: str,
    ) -> None:
        await self.session.execute(
            _UPSERT,
            {
                "uid": user_id,
                "work_style": work_style,
                "company_size_pref": company_size_pref,
                "work_type_pref": work_type_pref,
                "work_values": json.dumps(work_values or []),
                "source": source,
            },
        )
        await self.session.commit()
```

- [ ] **Step 4: PreferenceService 작성**

`domain/user_intelligence/hub/services/preference_service.py`:

```python
# 성향·선호 서비스 — disposition 선택 입력을 user_preferences 에 저장·조회

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from domain.user_intelligence.hub.repositories.preference_repository import PreferenceRepository

SOURCE_USER_FORM = "user_form"


class PreferenceService:
    def __init__(self, db: AsyncSession):
        self.repo = PreferenceRepository(db)

    async def get_preferences(self, user_id: str) -> dict:
        """없으면 전부 null/빈 기본값."""
        pref = await self.repo.fetch_preferences(user_id)
        if pref is None:
            return {
                "workStyle": None,
                "companySizePref": None,
                "workTypePref": None,
                "workValues": [],
                "source": None,
            }
        return {
            "workStyle": pref["work_style"],
            "companySizePref": pref["company_size_pref"],
            "workTypePref": pref["work_type_pref"],
            "workValues": pref["work_values"],
            "source": pref["source"],
        }

    async def upsert_preferences(
        self,
        user_id: str,
        work_style: str | None,
        company_size_pref: str | None,
        work_type_pref: str | None,
        work_values: list,
    ) -> dict:
        await self.repo.upsert_preferences(
            user_id,
            work_style=work_style,
            company_size_pref=company_size_pref,
            work_type_pref=work_type_pref,
            work_values=work_values,
            source=SOURCE_USER_FORM,
        )
        return {
            "workStyle": work_style,
            "companySizePref": company_size_pref,
            "workTypePref": work_type_pref,
            "workValues": work_values,
            "source": SOURCE_USER_FORM,
        }
```

- [ ] **Step 5: 라우터 작성**

`api/v1/preferences/__init__.py`:

```python
# 성향·선호 라우터 패키지
```

`api/v1/preferences/preferences_routor.py`:

```python
# 성향·선호(disposition) HTTP 라우터 — user_intelligence 선택 입력 수집

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from core.api_guards import get_authenticated_user_id
from core.database import get_db
from domain.user_intelligence.hub.services.preference_service import PreferenceService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/preferences", tags=["preferences"])


class PreferenceUpsertRequest(BaseModel):
    workStyle: str | None = None
    companySizePref: str | None = None
    workTypePref: str | None = None
    workValues: list[str] = Field(default_factory=list)


@router.get("")
async def get_preferences(
    user_id: str = Depends(get_authenticated_user_id),
    db: AsyncSession = Depends(get_db),
):
    """현재 사용자 성향·선호 — 없으면 빈 기본값."""
    try:
        preferences = await PreferenceService(db).get_preferences(user_id)
        return {"success": True, "preferences": preferences}
    except Exception as e:
        logger.error(f"성향 조회 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"성향 조회 실패: {str(e)}")


@router.put("")
async def upsert_preferences(
    request: PreferenceUpsertRequest,
    user_id: str = Depends(get_authenticated_user_id),
    db: AsyncSession = Depends(get_db),
):
    """성향·선호 upsert — 폼 저장(전부 선택)."""
    try:
        preferences = await PreferenceService(db).upsert_preferences(
            user_id,
            work_style=request.workStyle,
            company_size_pref=request.companySizePref,
            work_type_pref=request.workTypePref,
            work_values=request.workValues or [],
        )
        return {"success": True, "preferences": preferences}
    except Exception as e:
        logger.error(f"성향 저장 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"성향 저장 실패: {str(e)}")
```

- [ ] **Step 6: main.py 에 라우터 등록**

`main.py` 의 `from api.v1.persona.persona_routor import router as persona_v1_router` (라인 31) 다음에 추가:

```python
from api.v1.preferences.preferences_routor import router as preferences_v1_router
```

`app.include_router(persona_v1_router, prefix=API_V1_PREFIX)` (라인 105) 다음에 추가:

```python
app.include_router(preferences_v1_router, prefix=API_V1_PREFIX)
```

- [ ] **Step 7: 테스트 실행 → 통과 확인**

Run: `python scripts/preferences_endpoint_test.py`
Expected: PASS — 전 체크 PASS, FAIL=0.

- [ ] **Step 8: 커밋**

```bash
git add domain/user_intelligence/hub/repositories/preference_repository.py domain/user_intelligence/hub/services/preference_service.py api/v1/preferences/ main.py scripts/preferences_endpoint_test.py
git commit -m "feat(user): 성향·선호 GET/PUT /api/preferences 수직"
```

---

### Task 5: persona 스펙 확장 — repository·service·DTO + 테스트 보강

**Files:**
- Modify: `domain/user_intelligence/hub/repositories/persona_repository.py`
- Modify: `domain/user_intelligence/hub/services/persona_service.py`
- Modify: `api/v1/persona/persona_routor.py` (DTO 4필드 + 매핑)
- Modify: `scripts/persona_endpoint_test.py` (스펙 필드 체크 추가)

**Interfaces:**
- Consumes: Task 2 의 `user_personas` 4 신규 컬럼.
- Produces: `/api/persona` GET/PUT 가 `certifications`/`languages`/`links`/`projects` 를 라운드트립. (기존 skills/experiences/education/summary 호환 유지.)

- [ ] **Step 1: persona_endpoint_test.py 에 스펙 필드 체크 추가**

`scripts/persona_endpoint_test.py` 의 `payload` 딕셔너리(라인 52-57)에 4 키 추가:

```python
    payload = {
        "skills": [{"name": "Python", "level": "중급"}, {"name": "SQL", "level": "입문"}],
        "experiences": [{"title": "데이터 동아리", "description": "공공데이터 시각화", "period": "2025"}],
        "education": [{"school": "OO대", "major": "컴퓨터공학", "degree": "학사", "status": "재학"}],
        "summary": "엔드포인트 테스트 페르소나",
        "certifications": [{"name": "정보처리기사", "issuer": "큐넷", "year": "2024"}],
        "languages": [{"language": "영어", "test": "TOEIC", "score": "900"}],
        "links": [{"type": "github", "url": "https://github.com/test"}],
        "projects": [{"title": "추천엔진", "description": "벡터 검색", "role": "백엔드", "period": "2025", "tech_stack": ["FastAPI", "pgvector"]}],
    }
```

`r = await client.get("/api/persona")` (무토큰 401, 라인 77) **직전**에 스펙 라운드트립 체크 추가:

```python
        check("자격증 반영", (p.get("certifications") or [{}])[0].get("name") == "정보처리기사", str(p.get("certifications")))
        check("어학 반영", (p.get("languages") or [{}])[0].get("test") == "TOEIC")
        check("링크 반영", (p.get("links") or [{}])[0].get("type") == "github")
        check("프로젝트 tech_stack", "pgvector" in ((p.get("projects") or [{}])[0].get("tech_stack") or []))
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `python scripts/persona_endpoint_test.py`
Expected: FAIL — `자격증 반영` 등 신규 체크 실패(아직 저장/반환 안 됨).

- [ ] **Step 3: persona_repository.py 확장**

`_FETCH` SELECT 절에 4컬럼 추가:

```python
_FETCH = text(
    """
    SELECT education, experiences, skills, summary, source,
           certifications, languages, links, projects
    FROM user_personas
    WHERE user_id = CAST(:uid AS UUID)
    """
)
```

`_UPSERT` 의 컬럼·VALUES·DO UPDATE 에 4컬럼 추가:

```python
_UPSERT = text(
    """
    INSERT INTO user_personas
        (user_id, education, experiences, skills, summary, source,
         certifications, languages, links, projects, updated_at)
    VALUES (CAST(:uid AS UUID), CAST(:edu AS JSONB), CAST(:exp AS JSONB),
            CAST(:skl AS JSONB), :summary, :source,
            CAST(:cert AS JSONB), CAST(:lang AS JSONB), CAST(:links AS JSONB), CAST(:proj AS JSONB), now())
    ON CONFLICT (user_id) DO UPDATE SET
        education = EXCLUDED.education,
        experiences = EXCLUDED.experiences,
        skills = EXCLUDED.skills,
        summary = EXCLUDED.summary,
        source = EXCLUDED.source,
        certifications = EXCLUDED.certifications,
        languages = EXCLUDED.languages,
        links = EXCLUDED.links,
        projects = EXCLUDED.projects,
        updated_at = now()
    """
)
```

`fetch_persona` 의 반환 dict 에 4키 추가:

```python
        return {
            "education": r.education or [],
            "experiences": r.experiences or [],
            "skills": r.skills or [],
            "summary": r.summary or "",
            "source": r.source,
            "certifications": r.certifications or [],
            "languages": r.languages or [],
            "links": r.links or [],
            "projects": r.projects or [],
        }
```

`upsert_persona` 시그니처·파라미터 바인딩에 4 인자 추가:

```python
    async def upsert_persona(
        self,
        user_id: str,
        education: list,
        experiences: list,
        skills: list,
        summary: str,
        source: str,
        certifications: list,
        languages: list,
        links: list,
        projects: list,
    ) -> None:
        await self.session.execute(
            _UPSERT,
            {
                "uid": user_id,
                "edu": json.dumps(education or []),
                "exp": json.dumps(experiences or []),
                "skl": json.dumps(skills or []),
                "summary": summary or "",
                "source": source,
                "cert": json.dumps(certifications or []),
                "lang": json.dumps(languages or []),
                "links": json.dumps(links or []),
                "proj": json.dumps(projects or []),
            },
        )
        await self.session.commit()
```

- [ ] **Step 4: persona_service.py 확장**

`get_persona` 의 두 반환(빈 기본값·존재 분기) 에 4키 추가. 빈 기본값:

```python
        if persona is None:
            return {
                "skills": [], "experiences": [], "education": [], "summary": "", "source": None,
                "certifications": [], "languages": [], "links": [], "projects": [],
            }
        return {
            "skills": persona["skills"],
            "experiences": persona["experiences"],
            "education": persona["education"],
            "summary": persona["summary"],
            "source": persona["source"],
            "certifications": persona["certifications"],
            "languages": persona["languages"],
            "links": persona["links"],
            "projects": persona["projects"],
        }
```

`upsert_persona` 시그니처에 4 인자(기본값 `None`) 추가·repo 호출·반환 확장:

```python
    async def upsert_persona(
        self,
        user_id: str,
        skills: list,
        experiences: list,
        education: list,
        summary: str,
        certifications: list | None = None,
        languages: list | None = None,
        links: list | None = None,
        projects: list | None = None,
    ) -> dict:
        await self.repo.upsert_persona(
            user_id,
            education=education,
            experiences=experiences,
            skills=skills,
            summary=summary,
            source=SOURCE_USER_FORM,
            certifications=certifications or [],
            languages=languages or [],
            links=links or [],
            projects=projects or [],
        )
        return {
            "skills": skills,
            "experiences": experiences,
            "education": education,
            "summary": summary,
            "source": SOURCE_USER_FORM,
            "certifications": certifications or [],
            "languages": languages or [],
            "links": links or [],
            "projects": projects or [],
        }
```

- [ ] **Step 5: persona_routor.py DTO + 매핑 확장**

신규 항목 모델을 `PersonaUpsertRequest` 정의 앞에 추가:

```python
class CertificationItem(BaseModel):
    name: str
    issuer: str = ""
    year: str = ""


class LanguageItem(BaseModel):
    language: str
    test: str = ""
    score: str = ""


class LinkItem(BaseModel):
    type: str = ""  # github|portfolio|blog
    url: str = ""


class ProjectItem(BaseModel):
    title: str
    description: str = ""
    role: str = ""
    period: str = ""
    tech_stack: list[str] = Field(default_factory=list)
```

`PersonaUpsertRequest` 에 4 필드 추가:

```python
class PersonaUpsertRequest(BaseModel):
    skills: list[SkillItem] = Field(default_factory=list)
    experiences: list[ExperienceItem] = Field(default_factory=list)
    education: list[EducationItem] = Field(default_factory=list)
    summary: str = ""
    certifications: list[CertificationItem] = Field(default_factory=list)
    languages: list[LanguageItem] = Field(default_factory=list)
    links: list[LinkItem] = Field(default_factory=list)
    projects: list[ProjectItem] = Field(default_factory=list)
```

`upsert_persona` 호출에 4 인자 매핑 추가:

```python
        persona = await PersonaService(db).upsert_persona(
            user_id,
            skills=[s.model_dump() for s in request.skills],
            experiences=[e.model_dump() for e in request.experiences],
            education=[ed.model_dump() for ed in request.education],
            summary=request.summary,
            certifications=[c.model_dump() for c in request.certifications],
            languages=[lg.model_dump() for lg in request.languages],
            links=[lk.model_dump() for lk in request.links],
            projects=[pj.model_dump() for pj in request.projects],
        )
```

- [ ] **Step 6: 테스트 실행 → 통과 확인**

Run: `python scripts/persona_endpoint_test.py`
Expected: PASS — 기존 + 신규 4 체크 모두 PASS, FAIL=0.

- [ ] **Step 7: 커밋**

```bash
git add domain/user_intelligence/hub/repositories/persona_repository.py domain/user_intelligence/hub/services/persona_service.py api/v1/persona/persona_routor.py scripts/persona_endpoint_test.py
git commit -m "feat(user): persona 스펙 4필드(자격증·어학·링크·프로젝트) 확장"
```

---

## Phase 1 완료 기준

- `scripts/user_models_import_test.py`·`profile_endpoint_test.py`·`preferences_endpoint_test.py`·`persona_endpoint_test.py` 전부 FAIL=0.
- Neon head = `a3f7c1e9d2b4`.
- 등록 라우터에 `preferences` 추가, `/api/user/profile` 동작.
- 모든 신규 필드 nullable·부분 입력 허용 확인(profile 테스트의 gender null 케이스).

## Phase 1 범위 밖(후속 플랜)

- **Phase 2** — `_user_text()` 임베딩 직렬화 확장 + embed_repository JOIN + 재임베딩 보장 + Chance 키워드 가산. enum→한국어 라벨 매핑 순수함수.
- **Phase 3** — 프론트 프로필 선택 섹션 + 완성도 미터 + `/onboarding` + 키워드 풀 재설계.
- 키워드 고도화(sync-profile 선택지 재설계)는 스키마 무변경 → Phase 3 프론트에서.
