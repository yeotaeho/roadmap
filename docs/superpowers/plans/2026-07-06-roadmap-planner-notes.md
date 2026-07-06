# Roadmap 플래너(WBS)·노트 탭 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Roadmap 탭에 플래너(백로그·스프린트 보드 + 주간 간트 타임라인)와 노트(마크다운 + `[[링크]]` + 백링크) 탭을 풀스택으로 추가한다.

**Architecture:** hrowth_journey 도메인에 테이블 3개(`planner_sprints`·`planner_tasks`·`roadmap_notes`)와 서비스·리포지토리를 추가하고, 기존 `/api/v1/roadmap` 라우터를 확장한다. 프론트는 기존 4탭 셸(`RoadmapNavContext`)에 planner/notes 탭을 추가하고, 간트는 CSS Grid 7열 자체 구현, 드래그는 dnd-kit, 마크다운은 react-markdown을 쓴다. AI 분해는 기존 `LlmClient` json_object 패턴 + 결정론 폴백.

**Tech Stack:** FastAPI + SQLAlchemy(AsyncSession, raw SQL text()) + Alembic / Next.js 16 + React 19 + TanStack Query + Tailwind + framer-motion + @dnd-kit + react-markdown

**스펙:** `docs/superpowers/specs/2026-07-06-roadmap-planner-notes-design.md`

## Global Constraints

- 작업 브랜치: `feat/roadmap-planner-notes` — 현재 `feat/coach-chat-core`에서 분기 (alembic head `a3c9e5f7b2d1`이 이 브랜치에만 있음).
- 새 소스 파일 첫 줄: 한 줄 한국어 주석으로 역할 명시 (CLAUDE.md 규칙 6).
- 한국어 문장 종결은 `.` `?` `!` 만 (규칙 5).
- 백엔드 테스트 컨벤션: `backend/scripts/<name>_test.py` — `check(name, cond)` + 전역 PASS/FAIL, `python scripts/<name>_test.py`로 실행 (기존 `roadmap_planner_parse_test.py` 스타일). 순수 함수만 무DB 테스트.
- 프론트에는 테스트 스크립트가 없음 — 검증은 `pnpm lint` + `pnpm build` + Claude Preview 라이브 확인.
- API 응답 JSON은 camelCase (기존 `completedQuestIds` 컨벤션), DB 컬럼은 snake_case.
- 라우터 요청 모델은 기존 패턴대로 `roadmap_routor.py` 안에 인라인 Pydantic으로 정의.
- 커밋 메시지: 한국어 시맨틱 커밋 (`feat(roadmap): …`), 말미에 `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- alembic 새 revision id: `e7b3a1c5d9f2`, down_revision: `a3c9e5f7b2d1`.
- 백엔드 실행 루트는 `backend/` (모든 python·alembic 명령은 backend 디렉터리에서).

---

### Task 1: 브랜치 + 마이그레이션 + ORM 모델

**Files:**
- Create: `backend/alembic/versions/e7b3a1c5d9f2_add_planner_and_notes_tables.py`
- Create: `backend/domain/hrowth_journey/models/bases/planner_sprint.py`
- Create: `backend/domain/hrowth_journey/models/bases/planner_task.py`
- Create: `backend/domain/hrowth_journey/models/bases/roadmap_note.py`
- Modify: `backend/alembic/env.py:84` (모델 import 3줄 추가)

**Interfaces:**
- Produces: 테이블 `planner_sprints`(id, user_id, title, goal, start_date, end_date, state, position), `planner_tasks`(id, user_id, sprint_id NULL=백로그, quest_key, title, description, status, start_date, due_date, estimated_days, position, source), `roadmap_notes`(id, user_id, title UNIQUE per user, content, linked_titles JSONB, task_id, quest_key). 후속 태스크의 raw SQL이 이 컬럼명을 그대로 사용.
- sprint 삭제 → 소속 태스크 백로그 복귀는 FK `ondelete="SET NULL"`로 DB가 보장.

- [ ] **Step 1: 브랜치 생성**

```powershell
git checkout -b feat/roadmap-planner-notes
```

- [ ] **Step 2: 마이그레이션 파일 작성**

`backend/alembic/versions/e7b3a1c5d9f2_add_planner_and_notes_tables.py`:

```python
"""planner_sprints·planner_tasks·roadmap_notes 테이블을 생성한다."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "e7b3a1c5d9f2"
down_revision: Union[str, None] = "a3c9e5f7b2d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 스프린트 — 기간 단위 태스크 묶음 ──
    op.create_table(
        "planner_sprints",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("goal", sa.Text(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("state", sa.String(length=12), server_default="planned", nullable=False),
        sa.Column("position", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_planner_sprint_user", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        comment="플래너 스프린트 — 기간 단위 태스크 묶음",
    )
    op.create_index("ix_planner_sprints_user", "planner_sprints", ["user_id"], unique=False)

    # ── 태스크 — sprint_id NULL 이면 백로그 ──
    op.create_table(
        "planner_tasks",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sprint_id", sa.BigInteger(), nullable=True),
        sa.Column("quest_key", sa.String(length=60), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=10), server_default="todo", nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("estimated_days", sa.Integer(), nullable=True),
        sa.Column("position", sa.Integer(), server_default="0", nullable=False),
        sa.Column("source", sa.String(length=10), server_default="user", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_planner_task_user", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["sprint_id"],
            ["planner_sprints.id"],
            name="fk_planner_task_sprint",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        comment="플래너 태스크 — sprint_id NULL 이면 백로그, quest_key 느슨한 참조",
    )
    op.create_index("ix_planner_tasks_user", "planner_tasks", ["user_id"], unique=False)
    op.create_index("ix_planner_tasks_sprint", "planner_tasks", ["sprint_id"], unique=False)

    # ── 노트 — [[제목]] 링크가 제목으로 해석되므로 사용자×제목 유니크 ──
    op.create_table(
        "roadmap_notes",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("content", sa.Text(), server_default="", nullable=False),
        sa.Column("linked_titles", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("task_id", sa.BigInteger(), nullable=True),
        sa.Column("quest_key", sa.String(length=60), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_roadmap_note_user", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["task_id"], ["planner_tasks.id"], name="fk_roadmap_note_task", ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "title", name="uq_roadmap_note_title"),
        comment="로드맵 노트 — 마크다운 + [[링크]] 파싱 캐시",
    )
    op.create_index("ix_roadmap_notes_user", "roadmap_notes", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_roadmap_notes_user", table_name="roadmap_notes")
    op.drop_table("roadmap_notes")
    op.drop_index("ix_planner_tasks_sprint", table_name="planner_tasks")
    op.drop_index("ix_planner_tasks_user", table_name="planner_tasks")
    op.drop_table("planner_tasks")
    op.drop_index("ix_planner_sprints_user", table_name="planner_sprints")
    op.drop_table("planner_sprints")
```

- [ ] **Step 3: ORM 모델 3개 작성** (기존 `user_roadmap.py` 스타일)

`backend/domain/hrowth_journey/models/bases/planner_sprint.py`:

```python
# 플래너 스프린트 ORM — 기간 단위 태스크 묶음

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from core.database import Base


class PlannerSprint(Base):
    __tablename__ = "planner_sprints"
    __table_args__ = ({"comment": "플래너 스프린트 — 기간 단위 태스크 묶음"},)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", name="fk_planner_sprint_user", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    goal: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    # planned | active | done
    state: Mapped[str] = mapped_column(String(12), nullable=False, server_default="planned")
    position: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
```

`backend/domain/hrowth_journey/models/bases/planner_task.py`:

```python
# 플래너 태스크 ORM — sprint_id NULL 이면 백로그, quest_key 느슨한 참조

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from core.database import Base


class PlannerTask(Base):
    __tablename__ = "planner_tasks"
    __table_args__ = (
        {"comment": "플래너 태스크 — sprint_id NULL 이면 백로그, quest_key 느슨한 참조"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", name="fk_planner_task_user", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sprint_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("planner_sprints.id", name="fk_planner_task_sprint", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    quest_key: Mapped[str | None] = mapped_column(String(60), nullable=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # todo | doing | done
    status: Mapped[str] = mapped_column(String(10), nullable=False, server_default="todo")
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    estimated_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    # user | ai
    source: Mapped[str] = mapped_column(String(10), nullable=False, server_default="user")
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
```

`backend/domain/hrowth_journey/models/bases/roadmap_note.py`:

```python
# 로드맵 노트 ORM — 마크다운 + [[링크]] 파싱 캐시, 사용자×제목 유니크

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from core.database import Base


class RoadmapNote(Base):
    __tablename__ = "roadmap_notes"
    __table_args__ = (
        UniqueConstraint("user_id", "title", name="uq_roadmap_note_title"),
        {"comment": "로드맵 노트 — 마크다운 + [[링크]] 파싱 캐시"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", name="fk_roadmap_note_user", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    # 저장 시 [[...]] 파싱 결과 캐시 [str] — 백링크 조회용
    linked_titles: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    task_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("planner_tasks.id", name="fk_roadmap_note_task", ondelete="SET NULL"),
        nullable=True,
    )
    quest_key: Mapped[str | None] = mapped_column(String(60), nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
```

- [ ] **Step 4: `backend/alembic/env.py` 모델 import 추가** — 84행 `GrowthLog` import 바로 아래에:

```python
from domain.hrowth_journey.models.bases.planner_sprint import PlannerSprint  # Roadmap 플래너
from domain.hrowth_journey.models.bases.planner_task import PlannerTask  # Roadmap 플래너
from domain.hrowth_journey.models.bases.roadmap_note import RoadmapNote  # Roadmap 노트
```

- [ ] **Step 5: 마이그레이션 적용 및 확인**

Run (backend/ 에서): `alembic upgrade head`
Expected: `Running upgrade a3c9e5f7b2d1 -> e7b3a1c5d9f2` 출력, 에러 없음.

Run: `alembic current`
Expected: `e7b3a1c5d9f2 (head)`

- [ ] **Step 6: 커밋**

```powershell
git add backend/alembic/versions/e7b3a1c5d9f2_add_planner_and_notes_tables.py backend/domain/hrowth_journey/models/bases/planner_sprint.py backend/domain/hrowth_journey/models/bases/planner_task.py backend/domain/hrowth_journey/models/bases/roadmap_note.py backend/alembic/env.py
git commit -m "feat(roadmap): 플래너·노트 테이블 3종 마이그레이션 + ORM 모델"
```

---

### Task 2: LlmClient 퀘스트 분해 — 프롬프트·파서·메서드 (TDD)

**Files:**
- Modify: `backend/core/llm/client.py` (모듈 상수 `_DECOMPOSE_SYSTEM_PROMPT`, 순수 파서 `_parse_decompose`, 메서드 `decompose_quest` 추가 — `_ROADMAP_SYSTEM_PROMPT`·`generate_roadmap` 근처)
- Test: `backend/scripts/planner_decompose_parse_test.py`

**Interfaces:**
- Produces: `_parse_decompose(raw: str | None) -> list[dict]` — 각 dict는 `{title: str(≤200), description: str, estimated_days: int(1~30, 기본 3)}`, 최대 6개, 무효 시 `[]`.
- Produces: `async LlmClient.decompose_quest(context: str) -> list[dict]` — 동일 스키마.

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/scripts/planner_decompose_parse_test.py`:

```python
# 퀘스트 분해 파서·폴백 템플릿 무DB 검증 테스트

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.llm.client import _parse_decompose  # noqa: E402

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


_VALID = json.dumps(
    {
        "tasks": [
            {"title": "지표 용어집 정리", "description": "핵심 지표 20개", "estimated_days": 2},
            {"title": "데이터 소스 목록화", "description": "", "estimated_days": 99},
            {"title": "  ", "description": "제목 공백 — 버려야 함", "estimated_days": 3},
            {"title": "미니 파이프라인", "description": "입력→검증→저장", "estimated_days": "5"},
            {"title": "A", "estimated_days": 1},
            {"title": "B", "estimated_days": 1},
            {"title": "C", "estimated_days": 1},
            {"title": "7번째 — 잘려야 함", "estimated_days": 1},
        ]
    }
)


def test_valid() -> None:
    r = _parse_decompose(_VALID)
    check("최대 6개 상한", len(r) <= 6)
    check("공백 제목 제거", all(t["title"].strip() for t in r))
    check("estimated_days 범위 밖 보정(99→3)", r[1]["estimated_days"] == 3)
    check("estimated_days 비정수 보정('5'→3)", r[2]["estimated_days"] == 3)
    check("첫 항목 보존", r[0]["title"] == "지표 용어집 정리" and r[0]["estimated_days"] == 2)


def test_invalid() -> None:
    check("None → []", _parse_decompose(None) == [])
    check("깨진 JSON → []", _parse_decompose("{not json") == [])
    check("tasks 없음 → []", _parse_decompose(json.dumps({"foo": 1})) == [])
    check("tasks 비리스트 → []", _parse_decompose(json.dumps({"tasks": "x"})) == [])


if __name__ == "__main__":
    test_valid()
    test_invalid()
    print(f"\n결과: PASS {PASS} / FAIL {FAIL}")
    sys.exit(1 if FAIL else 0)
```

- [ ] **Step 2: 실패 확인**

Run (backend/ 에서): `python scripts/planner_decompose_parse_test.py`
Expected: `ImportError: cannot import name '_parse_decompose'`

- [ ] **Step 3: client.py 구현** — `_ROADMAP_SYSTEM_PROMPT` 상수 근처에 프롬프트 추가:

```python
_DECOMPOSE_SYSTEM_PROMPT = """당신은 진로 성장 플래너입니다. 주어진 퀘스트(학습 과제)를 실행 가능한 태스크 3~6개로 분해하세요.

규칙:
- 각 태스크는 1~2주 안에 혼자 끝낼 수 있는 구체적 행동 단위여야 합니다.
- title 은 25자 이내 한국어 동사형, description 은 산출물이 드러나는 1문장.
- estimated_days 는 1~30 사이 정수.
- 반드시 JSON 으로만 응답: {"tasks": [{"title": str, "description": str, "estimated_days": int}]}
"""
```

순수 파서를 모듈 레벨(다른 `_parse_*` 함수들 근처)에 추가:

```python
def _parse_decompose(raw: str | None) -> list[dict]:
    """퀘스트 분해 응답 JSON → 태스크 목록. 무효/실패 시 []."""
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
    items = data.get("tasks") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return []
    out: list[dict] = []
    for it in items:
        if len(out) >= 6:
            break
        if not isinstance(it, dict):
            continue
        title = str(it.get("title") or "").strip()
        if not title:
            continue
        days = it.get("estimated_days")
        if not isinstance(days, int) or isinstance(days, bool) or not (1 <= days <= 30):
            days = 3
        out.append(
            {
                "title": title[:200],
                "description": str(it.get("description") or "").strip(),
                "estimated_days": days,
            }
        )
    return out
```

`LlmClient` 클래스의 `generate_roadmap` 아래에 메서드 추가:

```python
    async def decompose_quest(self, context: str) -> list[dict]:
        """퀘스트 맥락을 실행 태스크 3~6개로 분해한다. 무효/실패 시 []."""
        resp = await self._client.chat.completions.create(
            model=self._model,
            temperature=0.3,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _DECOMPOSE_SYSTEM_PROMPT},
                {"role": "user", "content": context},
            ],
        )
        return _parse_decompose(resp.choices[0].message.content)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python scripts/planner_decompose_parse_test.py`
Expected: `결과: PASS 9 / FAIL 0`, exit 0

- [ ] **Step 5: 커밋**

```powershell
git add backend/core/llm/client.py backend/scripts/planner_decompose_parse_test.py
git commit -m "feat(roadmap): LlmClient 퀘스트 분해 — 프롬프트·파서·decompose_quest"
```

---

### Task 3: 플래너 리포지토리 + 서비스 (스프린트·태스크 CRUD·reorder·분해 폴백)

**Files:**
- Create: `backend/domain/hrowth_journey/hub/repositories/planner_repository.py`
- Create: `backend/domain/hrowth_journey/hub/services/planner_service.py`
- Test: `backend/scripts/planner_service_test.py`

**Interfaces:**
- Consumes: Task 1 테이블, Task 2 `LlmClient.decompose_quest`.
- Produces: `PlannerService(db)` — `get_board(user_id) -> dict`, `create_sprint(user_id, payload) -> dict`, `update_sprint(user_id, sprint_id, fields) -> bool`, `delete_sprint(user_id, sprint_id) -> bool`, `create_task(user_id, payload) -> dict`, `update_task(user_id, task_id, fields) -> bool`, `delete_task(user_id, task_id) -> bool`, `reorder_tasks(user_id, sprint_id, task_ids) -> int`, `decompose(user_id, quest_key) -> dict`.
- Produces(순수): `template_decompose(quest: dict) -> list[dict]`, `serialize_sprint(row: dict) -> dict`, `serialize_task(row: dict) -> dict` (camelCase 변환 — Task 4 라우터와 Task 6 프론트 타입이 이 키를 사용).
- 직렬화 키: sprint `{id,title,goal,startDate,endDate,state,position}` / task `{id,sprintId,questKey,title,description,status,startDate,dueDate,estimatedDays,position,source}` (날짜는 `YYYY-MM-DD` 문자열 또는 null).

- [ ] **Step 1: 실패하는 테스트 작성** — 순수 함수(직렬화·폴백 템플릿)만 무DB 검증.

`backend/scripts/planner_service_test.py`:

```python
# 플래너 서비스 순수 함수(직렬화·분해 폴백) 무DB 검증 테스트

from __future__ import annotations

import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from domain.hrowth_journey.hub.services.planner_service import (  # noqa: E402
    serialize_sprint,
    serialize_task,
    template_decompose,
)

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


def test_serialize() -> None:
    s = serialize_sprint(
        {"id": 1, "title": "1주차", "goal": None, "start_date": date(2026, 7, 6),
         "end_date": date(2026, 7, 12), "state": "active", "position": 0}
    )
    check("sprint camelCase", s["startDate"] == "2026-07-06" and s["endDate"] == "2026-07-12")
    check("sprint goal None 유지", s["goal"] is None)

    t = serialize_task(
        {"id": 9, "sprint_id": None, "quest_key": "q-a", "title": "t", "description": "",
         "status": "todo", "start_date": None, "due_date": date(2026, 7, 10),
         "estimated_days": 3, "position": 2, "source": "ai"}
    )
    check("task 백로그 sprintId null", t["sprintId"] is None)
    check("task dueDate 직렬화", t["dueDate"] == "2026-07-10" and t["startDate"] is None)
    check("task 나머지 키", t["questKey"] == "q-a" and t["estimatedDays"] == 3 and t["source"] == "ai")


def test_template_decompose() -> None:
    r = template_decompose({"title": "탄소 스키마", "difficulty": "중급", "purpose": "p"})
    check("폴백 3개", len(r) == 3)
    check("폴백 제목에 퀘스트 반영", any("탄소 스키마" in t["title"] for t in r))
    check("폴백 estimated_days 범위", all(1 <= t["estimated_days"] <= 30 for t in r))
    r2 = template_decompose({})
    check("빈 퀘스트도 3개 폴백", len(r2) == 3)


if __name__ == "__main__":
    test_serialize()
    test_template_decompose()
    print(f"\n결과: PASS {PASS} / FAIL {FAIL}")
    sys.exit(1 if FAIL else 0)
```

- [ ] **Step 2: 실패 확인**

Run: `python scripts/planner_service_test.py`
Expected: `ModuleNotFoundError: No module named 'domain.hrowth_journey.hub.services.planner_service'`

- [ ] **Step 3: 리포지토리 구현**

`backend/domain/hrowth_journey/hub/repositories/planner_repository.py`:

```python
# 플래너 리포지토리 — planner_sprints·planner_tasks 조회·CRUD·재정렬

from __future__ import annotations

from datetime import date

from sqlalchemy import text

from domain.auth.hub.repositories.base_repository import BaseRepository

_FETCH_SPRINTS = text(
    """
    SELECT id, title, goal, start_date, end_date, state, position
    FROM planner_sprints
    WHERE user_id = CAST(:user_id AS UUID)
    ORDER BY position, start_date, id
    """
)

_FETCH_TASKS = text(
    """
    SELECT id, sprint_id, quest_key, title, description, status,
           start_date, due_date, estimated_days, position, source
    FROM planner_tasks
    WHERE user_id = CAST(:user_id AS UUID)
    ORDER BY position, id
    """
)

_INSERT_SPRINT = text(
    """
    INSERT INTO planner_sprints (user_id, title, goal, start_date, end_date, state, position)
    VALUES (CAST(:user_id AS UUID), :title, :goal, :start_date, :end_date, :state,
            COALESCE((SELECT MAX(position) + 1 FROM planner_sprints
                      WHERE user_id = CAST(:user_id AS UUID)), 0))
    RETURNING id, title, goal, start_date, end_date, state, position
    """
)

_DELETE_SPRINT = text(
    """
    DELETE FROM planner_sprints
    WHERE id = :sprint_id AND user_id = CAST(:user_id AS UUID)
    """
)

_INSERT_TASK = text(
    """
    INSERT INTO planner_tasks
        (user_id, sprint_id, quest_key, title, description, status,
         start_date, due_date, estimated_days, position, source)
    VALUES (CAST(:user_id AS UUID), :sprint_id, :quest_key, :title, :description, :status,
            :start_date, :due_date, :estimated_days,
            COALESCE((SELECT MAX(position) + 1 FROM planner_tasks
                      WHERE user_id = CAST(:user_id AS UUID)
                        AND sprint_id IS NOT DISTINCT FROM :sprint_id), 0),
            :source)
    RETURNING id, sprint_id, quest_key, title, description, status,
              start_date, due_date, estimated_days, position, source
    """
)

_DELETE_TASK = text(
    """
    DELETE FROM planner_tasks
    WHERE id = :task_id AND user_id = CAST(:user_id AS UUID)
    """
)

_REORDER_TASK = text(
    """
    UPDATE planner_tasks
    SET sprint_id = :sprint_id, position = :position, updated_at = now()
    WHERE id = :task_id AND user_id = CAST(:user_id AS UUID)
    """
)

# 퀘스트 조회 — 사용자 활성 로드맵에서 quest_key 매칭(분해 컨텍스트용)
_FETCH_QUEST = text(
    """
    SELECT q.quest_key, q.title, q.purpose, q.difficulty, q.keywords
    FROM roadmap_quests q
    JOIN user_roadmaps r ON r.id = q.roadmap_id
    WHERE r.user_id = CAST(:user_id AS UUID) AND q.quest_key = :quest_key
    """
)

# 부분 수정 허용 컬럼 화이트리스트 — SQL 조립은 이 키에 한정
_SPRINT_FIELDS = {"title", "goal", "start_date", "end_date", "state", "position"}
_TASK_FIELDS = {
    "sprint_id", "quest_key", "title", "description", "status",
    "start_date", "due_date", "estimated_days", "position",
}


class PlannerRepository(BaseRepository):
    async def fetch_sprints(self, user_id: str) -> list[dict]:
        rows = (await self.session.execute(_FETCH_SPRINTS, {"user_id": user_id})).mappings().all()
        return [dict(r) for r in rows]

    async def fetch_tasks(self, user_id: str) -> list[dict]:
        rows = (await self.session.execute(_FETCH_TASKS, {"user_id": user_id})).mappings().all()
        return [dict(r) for r in rows]

    async def insert_sprint(
        self, user_id: str, title: str, goal: str | None,
        start_date: date, end_date: date, state: str,
    ) -> dict:
        row = (
            await self.session.execute(
                _INSERT_SPRINT,
                {"user_id": user_id, "title": title, "goal": goal,
                 "start_date": start_date, "end_date": end_date, "state": state},
            )
        ).mappings().one()
        await self.session.commit()
        return dict(row)

    async def update_sprint(self, user_id: str, sprint_id: int, fields: dict) -> bool:
        return await self._update("planner_sprints", _SPRINT_FIELDS, user_id, sprint_id, fields)

    async def delete_sprint(self, user_id: str, sprint_id: int) -> bool:
        res = await self.session.execute(
            _DELETE_SPRINT, {"user_id": user_id, "sprint_id": sprint_id}
        )
        await self.session.commit()
        return res.rowcount > 0

    async def insert_task(self, user_id: str, fields: dict) -> dict:
        params = {
            "user_id": user_id,
            "sprint_id": fields.get("sprint_id"),
            "quest_key": fields.get("quest_key"),
            "title": fields["title"],
            "description": fields.get("description"),
            "status": fields.get("status") or "todo",
            "start_date": fields.get("start_date"),
            "due_date": fields.get("due_date"),
            "estimated_days": fields.get("estimated_days"),
            "source": fields.get("source") or "user",
        }
        row = (await self.session.execute(_INSERT_TASK, params)).mappings().one()
        await self.session.commit()
        return dict(row)

    async def update_task(self, user_id: str, task_id: int, fields: dict) -> bool:
        return await self._update("planner_tasks", _TASK_FIELDS, user_id, task_id, fields)

    async def delete_task(self, user_id: str, task_id: int) -> bool:
        res = await self.session.execute(_DELETE_TASK, {"user_id": user_id, "task_id": task_id})
        await self.session.commit()
        return res.rowcount > 0

    async def reorder_tasks(
        self, user_id: str, sprint_id: int | None, task_ids: list[int]
    ) -> int:
        """task_ids 순서대로 position 0..n 재부여 + 대상 컬럼(sprint_id)로 이동."""
        moved = 0
        for pos, tid in enumerate(task_ids):
            res = await self.session.execute(
                _REORDER_TASK,
                {"user_id": user_id, "sprint_id": sprint_id, "position": pos, "task_id": tid},
            )
            moved += res.rowcount
        await self.session.commit()
        return moved

    async def fetch_quest(self, user_id: str, quest_key: str) -> dict | None:
        row = (
            await self.session.execute(
                _FETCH_QUEST, {"user_id": user_id, "quest_key": quest_key}
            )
        ).mappings().first()
        return dict(row) if row else None

    async def _update(
        self, table: str, allowed: set[str], user_id: str, row_id: int, fields: dict
    ) -> bool:
        """화이트리스트 컬럼만 동적 SET. 값은 전부 바인드 파라미터."""
        sets = {k: v for k, v in fields.items() if k in allowed}
        if not sets:
            return False
        clause = ", ".join(f"{k} = :{k}" for k in sets)
        stmt = text(
            f"UPDATE {table} SET {clause}, updated_at = now() "
            "WHERE id = :row_id AND user_id = CAST(:user_id AS UUID)"
        )
        res = await self.session.execute(
            stmt, {**sets, "row_id": row_id, "user_id": user_id}
        )
        await self.session.commit()
        return res.rowcount > 0
```

- [ ] **Step 4: 서비스 구현**

`backend/domain/hrowth_journey/hub/services/planner_service.py`:

```python
# 플래너 서비스 — 보드 서빙·스프린트/태스크 CRUD·AI 퀘스트 분해(폴백 템플릿)

from __future__ import annotations

from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from core.config.settings import get_settings
from core.llm.client import LlmClient
from domain.hrowth_journey.hub.repositories.planner_repository import PlannerRepository


def _iso(d: date | None) -> str | None:
    return d.isoformat() if d else None


def serialize_sprint(row: dict) -> dict:
    """DB row(snake) → API 응답(camel)."""
    return {
        "id": row["id"],
        "title": row["title"],
        "goal": row["goal"],
        "startDate": _iso(row["start_date"]),
        "endDate": _iso(row["end_date"]),
        "state": row["state"],
        "position": row["position"],
    }


def serialize_task(row: dict) -> dict:
    """DB row(snake) → API 응답(camel)."""
    return {
        "id": row["id"],
        "sprintId": row["sprint_id"],
        "questKey": row["quest_key"],
        "title": row["title"],
        "description": row["description"] or "",
        "status": row["status"],
        "startDate": _iso(row["start_date"]),
        "dueDate": _iso(row["due_date"]),
        "estimatedDays": row["estimated_days"],
        "position": row["position"],
        "source": row["source"],
    }


def template_decompose(quest: dict) -> list[dict]:
    """LLM 미사용/실패 시 결정론 폴백 — 학습→실행→정리 3단계."""
    title = (quest.get("title") or "이 퀘스트").strip() or "이 퀘스트"
    return [
        {"title": f"{title} — 개념·자료 조사", "description": "핵심 개념과 참고 자료를 목록으로 정리합니다.",
         "estimated_days": 2},
        {"title": f"{title} — 실행·산출물 만들기", "description": "작게라도 동작하는 결과물 하나를 만듭니다.",
         "estimated_days": 5},
        {"title": f"{title} — 회고·노트 정리", "description": "배운 것과 막힌 지점을 노트로 남깁니다.",
         "estimated_days": 1},
    ]


def build_decompose_context(quest: dict, target_job: str | None) -> str:
    """LLM 입력 맥락 조립. 무네트워크 순수 함수."""
    keywords = quest.get("keywords") or []
    parts = [
        f"[목표 직무] {target_job or '미정'}",
        f"[퀘스트] {quest.get('title') or ''}",
        f"[목적] {quest.get('purpose') or ''}",
        f"[난이도] {quest.get('difficulty') or '입문'}",
        f"[키워드] {', '.join(keywords) if keywords else '없음'}",
    ]
    return "\n".join(parts)


class PlannerService:
    def __init__(self, db: AsyncSession):
        self.repo = PlannerRepository(db)
        settings = get_settings()
        self._model = settings.llm_classify_model
        self._api_key = settings.openai_api_key

    async def get_board(self, user_id: str) -> dict:
        sprints = await self.repo.fetch_sprints(user_id)
        tasks = await self.repo.fetch_tasks(user_id)
        return {
            "sprints": [serialize_sprint(s) for s in sprints],
            "tasks": [serialize_task(t) for t in tasks],
        }

    async def create_sprint(
        self, user_id: str, title: str, goal: str | None,
        start_date: date, end_date: date, state: str = "planned",
    ) -> dict:
        row = await self.repo.insert_sprint(user_id, title, goal, start_date, end_date, state)
        return serialize_sprint(row)

    async def update_sprint(self, user_id: str, sprint_id: int, fields: dict) -> bool:
        return await self.repo.update_sprint(user_id, sprint_id, fields)

    async def delete_sprint(self, user_id: str, sprint_id: int) -> bool:
        # 소속 태스크는 FK ON DELETE SET NULL 로 백로그 복귀
        return await self.repo.delete_sprint(user_id, sprint_id)

    async def create_task(self, user_id: str, fields: dict) -> dict:
        row = await self.repo.insert_task(user_id, fields)
        return serialize_task(row)

    async def update_task(self, user_id: str, task_id: int, fields: dict) -> bool:
        return await self.repo.update_task(user_id, task_id, fields)

    async def delete_task(self, user_id: str, task_id: int) -> bool:
        return await self.repo.delete_task(user_id, task_id)

    async def reorder_tasks(
        self, user_id: str, sprint_id: int | None, task_ids: list[int]
    ) -> int:
        return await self.repo.reorder_tasks(user_id, sprint_id, task_ids)

    async def decompose(self, user_id: str, quest_key: str) -> dict:
        """퀘스트 → 태스크 3~6개 분해 후 백로그 insert. 반환: {source, tasks}."""
        quest = await self.repo.fetch_quest(user_id, quest_key)
        if quest is None:
            return {"source": "none", "tasks": []}

        sync = await self.repo.fetch_sync_profile(user_id)
        items: list[dict] = []
        source = "template"
        if self._api_key:
            try:
                llm = LlmClient(api_key=self._api_key, model=self._model)
                items = await llm.decompose_quest(
                    build_decompose_context(quest, sync["target_job"])
                )
                if items:
                    source = "llm"
            except Exception:
                items = []
        if not items:
            items = template_decompose(quest)
            source = "template"

        created = []
        for it in items:
            row = await self.repo.insert_task(
                user_id,
                {
                    "quest_key": quest_key,
                    "title": it["title"],
                    "description": it.get("description") or None,
                    "estimated_days": it.get("estimated_days"),
                    "source": "ai",
                },
            )
            created.append(serialize_task(row))
        return {"source": source, "tasks": created}
```

주의: `fetch_sync_profile`은 `RoadmapRepository`에 있다. `PlannerRepository`가 상속·중복하지 않도록, `PlannerRepository`에 동일 쿼리 메서드를 추가한다 — Step 3 파일 하단 `fetch_quest` 아래에 다음을 포함할 것 (기존 `roadmap_repository.py`의 `_FETCH_SYNC_PROFILE`과 동일 SQL):

```python
_FETCH_SYNC_PROFILE = text(
    """
    SELECT target_job, interest_keywords
    FROM user_sync_profiles WHERE user_id = CAST(:user_id AS UUID)
    """
)
```

```python
    async def fetch_sync_profile(self, user_id: str) -> dict:
        r = (await self.session.execute(_FETCH_SYNC_PROFILE, {"user_id": user_id})).first()
        if r is None:
            return {"target_job": None, "interest_keywords": []}
        return {"target_job": r.target_job, "interest_keywords": r.interest_keywords or []}
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `python scripts/planner_service_test.py`
Expected: `결과: PASS 9 / FAIL 0`, exit 0

- [ ] **Step 6: 커밋**

```powershell
git add backend/domain/hrowth_journey/hub/repositories/planner_repository.py backend/domain/hrowth_journey/hub/services/planner_service.py backend/scripts/planner_service_test.py
git commit -m "feat(roadmap): 플래너 리포지토리·서비스 — 보드/CRUD/재정렬/AI 분해 폴백"
```

---

### Task 4: 노트 리포지토리 + 서비스 + `[[링크]]` 파서 (TDD)

**Files:**
- Create: `backend/domain/hrowth_journey/hub/repositories/note_repository.py`
- Create: `backend/domain/hrowth_journey/hub/services/note_service.py`
- Test: `backend/scripts/roadmap_note_links_test.py`

**Interfaces:**
- Produces(순수): `parse_note_links(content: str) -> list[str]` — `[[제목]]` 추출, 트림·중복 제거(순서 보존)·빈 문자열 제외·제목 120자 초과 제외.
- Produces: `NoteService(db)` — `list_notes(user_id) -> list[dict]`, `get_note(user_id, note_id) -> dict | None`(백링크 포함), `create_note(user_id, title, content, task_id, quest_key) -> dict`, `update_note(user_id, note_id, fields) -> dict | None`, `delete_note(user_id, note_id) -> bool`.
- 노트 직렬화 키: 목록 `{id,title,updatedAt,preview}` / 상세 `{id,title,content,linkedTitles,taskId,questKey,updatedAt,backlinks:[{id,title}]}`.
- 제목 중복(unique 위반)은 서비스에서 `IntegrityError`를 잡아 `ValueError("duplicate-title")`로 변환 — 라우터(Task 5)가 409로 매핑.

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/scripts/roadmap_note_links_test.py`:

```python
# 노트 [[링크]] 파서 무DB 검증 테스트

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from domain.hrowth_journey.hub.services.note_service import parse_note_links  # noqa: E402

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


def test_parse() -> None:
    check("기본 추출", parse_note_links("본문 [[스키마 노트]] 끝") == ["스키마 노트"])
    check(
        "복수 + 중복 제거(순서 보존)",
        parse_note_links("[[A]] 중간 [[B]] 그리고 [[A]]") == ["A", "B"],
    )
    check("트림", parse_note_links("[[  공백 제목  ]]") == ["공백 제목"])
    check("빈 링크 제외", parse_note_links("[[]] [[ ]]") == [])
    check("중첩 대괄호 비탐욕", parse_note_links("[[a]]b]]") == ["a"])
    check("없음 → []", parse_note_links("링크 없는 본문") == [])
    check("빈 본문 → []", parse_note_links("") == [])
    check("120자 초과 제목 제외", parse_note_links(f"[[{'가' * 121}]]") == [])


if __name__ == "__main__":
    test_parse()
    print(f"\n결과: PASS {PASS} / FAIL {FAIL}")
    sys.exit(1 if FAIL else 0)
```

- [ ] **Step 2: 실패 확인**

Run: `python scripts/roadmap_note_links_test.py`
Expected: `ModuleNotFoundError: No module named 'domain.hrowth_journey.hub.services.note_service'`

- [ ] **Step 3: 리포지토리 구현**

`backend/domain/hrowth_journey/hub/repositories/note_repository.py`:

```python
# 노트 리포지토리 — roadmap_notes CRUD·백링크 조회

from __future__ import annotations

import json

from sqlalchemy import text

from domain.auth.hub.repositories.base_repository import BaseRepository

_LIST_NOTES = text(
    """
    SELECT id, title, updated_at, LEFT(content, 80) AS preview
    FROM roadmap_notes
    WHERE user_id = CAST(:user_id AS UUID)
    ORDER BY updated_at DESC, id DESC
    """
)

_FETCH_NOTE = text(
    """
    SELECT id, title, content, linked_titles, task_id, quest_key, updated_at
    FROM roadmap_notes
    WHERE id = :note_id AND user_id = CAST(:user_id AS UUID)
    """
)

# 백링크 — linked_titles JSONB 배열이 :title_json(단일 원소 배열)을 포함하는 노트
_FETCH_BACKLINKS = text(
    """
    SELECT id, title
    FROM roadmap_notes
    WHERE user_id = CAST(:user_id AS UUID)
      AND linked_titles @> CAST(:title_json AS JSONB)
      AND id != :note_id
    ORDER BY updated_at DESC
    """
)

_INSERT_NOTE = text(
    """
    INSERT INTO roadmap_notes (user_id, title, content, linked_titles, task_id, quest_key)
    VALUES (CAST(:user_id AS UUID), :title, :content, CAST(:linked AS JSONB), :task_id, :quest_key)
    RETURNING id, title, content, linked_titles, task_id, quest_key, updated_at
    """
)

_UPDATE_NOTE = text(
    """
    UPDATE roadmap_notes
    SET title = :title, content = :content, linked_titles = CAST(:linked AS JSONB),
        task_id = :task_id, quest_key = :quest_key, updated_at = now()
    WHERE id = :note_id AND user_id = CAST(:user_id AS UUID)
    RETURNING id, title, content, linked_titles, task_id, quest_key, updated_at
    """
)

_DELETE_NOTE = text(
    "DELETE FROM roadmap_notes WHERE id = :note_id AND user_id = CAST(:user_id AS UUID)"
)


class NoteRepository(BaseRepository):
    async def list_notes(self, user_id: str) -> list[dict]:
        rows = (await self.session.execute(_LIST_NOTES, {"user_id": user_id})).mappings().all()
        return [dict(r) for r in rows]

    async def fetch_note(self, user_id: str, note_id: int) -> dict | None:
        row = (
            await self.session.execute(_FETCH_NOTE, {"user_id": user_id, "note_id": note_id})
        ).mappings().first()
        return dict(row) if row else None

    async def fetch_backlinks(self, user_id: str, title: str, note_id: int) -> list[dict]:
        rows = (
            await self.session.execute(
                _FETCH_BACKLINKS,
                {"user_id": user_id, "title_json": json.dumps([title]), "note_id": note_id},
            )
        ).mappings().all()
        return [dict(r) for r in rows]

    async def insert_note(
        self, user_id: str, title: str, content: str, linked: list[str],
        task_id: int | None, quest_key: str | None,
    ) -> dict:
        row = (
            await self.session.execute(
                _INSERT_NOTE,
                {"user_id": user_id, "title": title, "content": content,
                 "linked": json.dumps(linked), "task_id": task_id, "quest_key": quest_key},
            )
        ).mappings().one()
        await self.session.commit()
        return dict(row)

    async def update_note(
        self, user_id: str, note_id: int, title: str, content: str, linked: list[str],
        task_id: int | None, quest_key: str | None,
    ) -> dict | None:
        row = (
            await self.session.execute(
                _UPDATE_NOTE,
                {"user_id": user_id, "note_id": note_id, "title": title, "content": content,
                 "linked": json.dumps(linked), "task_id": task_id, "quest_key": quest_key},
            )
        ).mappings().first()
        await self.session.commit()
        return dict(row) if row else None

    async def delete_note(self, user_id: str, note_id: int) -> bool:
        res = await self.session.execute(_DELETE_NOTE, {"user_id": user_id, "note_id": note_id})
        await self.session.commit()
        return res.rowcount > 0
```

- [ ] **Step 4: 서비스 구현**

`backend/domain/hrowth_journey/hub/services/note_service.py`:

```python
# 노트 서비스 — 마크다운 노트 CRUD·[[링크]] 파싱·백링크

from __future__ import annotations

import re
from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from domain.hrowth_journey.hub.repositories.note_repository import NoteRepository

_LINK_RE = re.compile(r"\[\[([^\[\]]+?)\]\]")


def parse_note_links(content: str) -> list[str]:
    """본문에서 [[제목]] 링크를 추출한다. 트림·중복 제거(순서 보존)·빈/120자 초과 제외."""
    if not content:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for m in _LINK_RE.finditer(content):
        title = m.group(1).strip()
        if not title or len(title) > 120 or title in seen:
            continue
        seen.add(title)
        out.append(title)
    return out


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _serialize_list_item(row: dict) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "updatedAt": _iso(row["updated_at"]),
        "preview": (row["preview"] or "").replace("\n", " ").strip(),
    }


def _serialize_detail(row: dict, backlinks: list[dict]) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "content": row["content"],
        "linkedTitles": row["linked_titles"] or [],
        "taskId": row["task_id"],
        "questKey": row["quest_key"],
        "updatedAt": _iso(row["updated_at"]),
        "backlinks": [{"id": b["id"], "title": b["title"]} for b in backlinks],
    }


class NoteService:
    def __init__(self, db: AsyncSession):
        self.repo = NoteRepository(db)

    async def list_notes(self, user_id: str) -> list[dict]:
        return [_serialize_list_item(r) for r in await self.repo.list_notes(user_id)]

    async def get_note(self, user_id: str, note_id: int) -> dict | None:
        row = await self.repo.fetch_note(user_id, note_id)
        if row is None:
            return None
        backlinks = await self.repo.fetch_backlinks(user_id, row["title"], note_id)
        return _serialize_detail(row, backlinks)

    async def create_note(
        self, user_id: str, title: str, content: str = "",
        task_id: int | None = None, quest_key: str | None = None,
    ) -> dict:
        try:
            row = await self.repo.insert_note(
                user_id, title.strip(), content, parse_note_links(content), task_id, quest_key
            )
        except IntegrityError:
            await self.repo.session.rollback()
            raise ValueError("duplicate-title")
        return _serialize_detail(row, [])

    async def update_note(self, user_id: str, note_id: int, fields: dict) -> dict | None:
        current = await self.repo.fetch_note(user_id, note_id)
        if current is None:
            return None
        title = (fields.get("title") or current["title"]).strip()
        content = fields.get("content") if fields.get("content") is not None else current["content"]
        task_id = fields.get("task_id") if "task_id" in fields else current["task_id"]
        quest_key = fields.get("quest_key") if "quest_key" in fields else current["quest_key"]
        try:
            row = await self.repo.update_note(
                user_id, note_id, title, content, parse_note_links(content), task_id, quest_key
            )
        except IntegrityError:
            await self.repo.session.rollback()
            raise ValueError("duplicate-title")
        if row is None:
            return None
        backlinks = await self.repo.fetch_backlinks(user_id, row["title"], note_id)
        return _serialize_detail(row, backlinks)

    async def delete_note(self, user_id: str, note_id: int) -> bool:
        return await self.repo.delete_note(user_id, note_id)
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `python scripts/roadmap_note_links_test.py`
Expected: `결과: PASS 8 / FAIL 0`, exit 0

- [ ] **Step 6: 커밋**

```powershell
git add backend/domain/hrowth_journey/hub/repositories/note_repository.py backend/domain/hrowth_journey/hub/services/note_service.py backend/scripts/roadmap_note_links_test.py
git commit -m "feat(roadmap): 노트 리포지토리·서비스 — [[링크]] 파서·백링크"
```

---

### Task 5: 라우터 확장 — 플래너·노트 API 14개

**Files:**
- Modify: `backend/api/v1/roadmap/roadmap_routor.py` (기존 4개 엔드포인트 아래에 추가)

**Interfaces:**
- Consumes: Task 3 `PlannerService`, Task 4 `NoteService`.
- Produces (모두 `{"success": True, ...}` 래핑, 인증 `get_authenticated_user_id`):
  - `GET /roadmap/planner` → `{success, sprints, tasks}`
  - `POST /roadmap/planner/sprints` → `{success, sprint}` / `PATCH·DELETE /roadmap/planner/sprints/{sprint_id}`
  - `POST /roadmap/planner/tasks` → `{success, task}` / `PATCH·DELETE /roadmap/planner/tasks/{task_id}`
  - `POST /roadmap/planner/tasks/reorder` — `{sprintId: int|null, taskIds: [int]}` (드래그 후 대상 컬럼 전체 순서)
  - `POST /roadmap/planner/decompose` — `{questKey}` → `{success, source, tasks}`
  - `GET /roadmap/notes` → `{success, notes}` / `POST /roadmap/notes` → `{success, note}` (409: 제목 중복)
  - `GET·PUT·DELETE /roadmap/notes/{note_id}` (404: 없음, 409: 제목 중복)

- [ ] **Step 1: 라우터에 요청 모델·엔드포인트 추가** — `roadmap_routor.py` 상단 import에 `from domain.hrowth_journey.hub.services.note_service import NoteService`, `from domain.hrowth_journey.hub.services.planner_service import PlannerService` 추가 후, 파일 하단에:

```python
# ── 플래너(WBS) — 백로그·스프린트·태스크 ──


def _parse_iso_date(value: str, field: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail=f"{field} 형식은 YYYY-MM-DD 이어야 합니다.")


class SprintCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    goal: str | None = None
    startDate: str
    endDate: str


class SprintPatchRequest(BaseModel):
    title: str | None = Field(default=None, max_length=120)
    goal: str | None = None
    startDate: str | None = None
    endDate: str | None = None
    state: str | None = Field(default=None, pattern="^(planned|active|done)$")
    position: int | None = None


class TaskCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    sprintId: int | None = None
    questKey: str | None = Field(default=None, max_length=60)
    startDate: str | None = None
    dueDate: str | None = None
    estimatedDays: int | None = Field(default=None, ge=1, le=90)


class TaskPatchRequest(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    description: str | None = None
    sprintId: int | None = None
    questKey: str | None = Field(default=None, max_length=60)
    status: str | None = Field(default=None, pattern="^(todo|doing|done)$")
    startDate: str | None = None
    dueDate: str | None = None
    estimatedDays: int | None = Field(default=None, ge=1, le=90)
    position: int | None = None


class TaskReorderRequest(BaseModel):
    sprintId: int | None = None
    taskIds: list[int] = Field(default_factory=list)


class DecomposeRequest(BaseModel):
    questKey: str = Field(min_length=1, max_length=60)


def _sprint_fields(req: SprintPatchRequest) -> dict:
    """PATCH 부분수정 — 전달된 필드만 snake_case 로 변환."""
    raw = req.model_dump(exclude_unset=True)
    out: dict = {}
    if "title" in raw:
        out["title"] = raw["title"]
    if "goal" in raw:
        out["goal"] = raw["goal"]
    if "startDate" in raw:
        out["start_date"] = _parse_iso_date(raw["startDate"], "startDate")
    if "endDate" in raw:
        out["end_date"] = _parse_iso_date(raw["endDate"], "endDate")
    if "state" in raw:
        out["state"] = raw["state"]
    if "position" in raw:
        out["position"] = raw["position"]
    return out


def _task_fields(req: TaskPatchRequest) -> dict:
    raw = req.model_dump(exclude_unset=True)
    out: dict = {}
    for camel, snake in [
        ("title", "title"), ("description", "description"), ("sprintId", "sprint_id"),
        ("questKey", "quest_key"), ("status", "status"), ("estimatedDays", "estimated_days"),
        ("position", "position"),
    ]:
        if camel in raw:
            out[snake] = raw[camel]
    if "startDate" in raw:
        out["start_date"] = _parse_iso_date(raw["startDate"], "startDate") if raw["startDate"] else None
    if "dueDate" in raw:
        out["due_date"] = _parse_iso_date(raw["dueDate"], "dueDate") if raw["dueDate"] else None
    return out


@router.get("/planner")
async def get_planner_board(
    user_id: str = Depends(get_authenticated_user_id),
    db: AsyncSession = Depends(get_db),
):
    """플래너 보드 — 스프린트·태스크 전체를 1회 로드."""
    try:
        result = await PlannerService(db).get_board(user_id)
        return {"success": True, **result}
    except Exception as e:
        logger.error(f"플래너 보드 조회 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"플래너 보드 조회 실패: {str(e)}")


@router.post("/planner/sprints")
async def create_sprint(
    request: SprintCreateRequest,
    user_id: str = Depends(get_authenticated_user_id),
    db: AsyncSession = Depends(get_db),
):
    """스프린트 생성."""
    start = _parse_iso_date(request.startDate, "startDate")
    end = _parse_iso_date(request.endDate, "endDate")
    if end < start:
        raise HTTPException(status_code=400, detail="endDate 는 startDate 이후여야 합니다.")
    try:
        sprint = await PlannerService(db).create_sprint(
            user_id, request.title.strip(), request.goal, start, end
        )
        return {"success": True, "sprint": sprint}
    except Exception as e:
        logger.error(f"스프린트 생성 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"스프린트 생성 실패: {str(e)}")


@router.patch("/planner/sprints/{sprint_id}")
async def patch_sprint(
    sprint_id: int,
    request: SprintPatchRequest,
    user_id: str = Depends(get_authenticated_user_id),
    db: AsyncSession = Depends(get_db),
):
    """스프린트 부분 수정."""
    fields = _sprint_fields(request)
    if not fields:
        raise HTTPException(status_code=400, detail="수정할 필드가 없습니다.")
    try:
        ok = await PlannerService(db).update_sprint(user_id, sprint_id, fields)
    except Exception as e:
        logger.error(f"스프린트 수정 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"스프린트 수정 실패: {str(e)}")
    if not ok:
        raise HTTPException(status_code=404, detail="스프린트를 찾을 수 없습니다.")
    return {"success": True}


@router.delete("/planner/sprints/{sprint_id}")
async def delete_sprint(
    sprint_id: int,
    user_id: str = Depends(get_authenticated_user_id),
    db: AsyncSession = Depends(get_db),
):
    """스프린트 삭제 — 소속 태스크는 백로그로 복귀(FK SET NULL)."""
    try:
        ok = await PlannerService(db).delete_sprint(user_id, sprint_id)
    except Exception as e:
        logger.error(f"스프린트 삭제 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"스프린트 삭제 실패: {str(e)}")
    if not ok:
        raise HTTPException(status_code=404, detail="스프린트를 찾을 수 없습니다.")
    return {"success": True}


@router.post("/planner/tasks")
async def create_task(
    request: TaskCreateRequest,
    user_id: str = Depends(get_authenticated_user_id),
    db: AsyncSession = Depends(get_db),
):
    """태스크 생성(수동)."""
    fields = {
        "title": request.title.strip(),
        "description": request.description,
        "sprint_id": request.sprintId,
        "quest_key": request.questKey,
        "estimated_days": request.estimatedDays,
        "start_date": _parse_iso_date(request.startDate, "startDate") if request.startDate else None,
        "due_date": _parse_iso_date(request.dueDate, "dueDate") if request.dueDate else None,
    }
    try:
        task = await PlannerService(db).create_task(user_id, fields)
        return {"success": True, "task": task}
    except Exception as e:
        logger.error(f"태스크 생성 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"태스크 생성 실패: {str(e)}")


@router.patch("/planner/tasks/{task_id}")
async def patch_task(
    task_id: int,
    request: TaskPatchRequest,
    user_id: str = Depends(get_authenticated_user_id),
    db: AsyncSession = Depends(get_db),
):
    """태스크 부분 수정 — 이동(sprintId)·상태·일정."""
    fields = _task_fields(request)
    if not fields:
        raise HTTPException(status_code=400, detail="수정할 필드가 없습니다.")
    try:
        ok = await PlannerService(db).update_task(user_id, task_id, fields)
    except Exception as e:
        logger.error(f"태스크 수정 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"태스크 수정 실패: {str(e)}")
    if not ok:
        raise HTTPException(status_code=404, detail="태스크를 찾을 수 없습니다.")
    return {"success": True}


@router.delete("/planner/tasks/{task_id}")
async def delete_task(
    task_id: int,
    user_id: str = Depends(get_authenticated_user_id),
    db: AsyncSession = Depends(get_db),
):
    """태스크 삭제."""
    try:
        ok = await PlannerService(db).delete_task(user_id, task_id)
    except Exception as e:
        logger.error(f"태스크 삭제 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"태스크 삭제 실패: {str(e)}")
    if not ok:
        raise HTTPException(status_code=404, detail="태스크를 찾을 수 없습니다.")
    return {"success": True}


@router.post("/planner/tasks/reorder")
async def reorder_tasks(
    request: TaskReorderRequest,
    user_id: str = Depends(get_authenticated_user_id),
    db: AsyncSession = Depends(get_db),
):
    """드래그 결과 반영 — 대상 컬럼(sprintId)의 태스크 순서를 통째로 재부여."""
    if not request.taskIds:
        raise HTTPException(status_code=400, detail="taskIds 가 비어 있습니다.")
    try:
        moved = await PlannerService(db).reorder_tasks(user_id, request.sprintId, request.taskIds)
        return {"success": True, "moved": moved}
    except Exception as e:
        logger.error(f"태스크 재정렬 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"태스크 재정렬 실패: {str(e)}")


@router.post("/planner/decompose")
async def decompose_quest(
    request: DecomposeRequest,
    user_id: str = Depends(get_authenticated_user_id),
    db: AsyncSession = Depends(get_db),
):
    """퀘스트 → AI 태스크 분해(LLM, 폴백 템플릿) → 백로그 추가."""
    try:
        result = await PlannerService(db).decompose(user_id, request.questKey)
    except Exception as e:
        logger.error(f"퀘스트 분해 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"퀘스트 분해 실패: {str(e)}")
    if result["source"] == "none":
        raise HTTPException(status_code=404, detail="해당 퀘스트를 찾을 수 없습니다.")
    return {"success": True, **result}


# ── 노트 — 마크다운 + [[링크]] ──


class NoteCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    content: str = ""
    taskId: int | None = None
    questKey: str | None = Field(default=None, max_length=60)


class NoteUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    content: str | None = None
    taskId: int | None = None
    questKey: str | None = Field(default=None, max_length=60)


@router.get("/notes")
async def list_notes(
    user_id: str = Depends(get_authenticated_user_id),
    db: AsyncSession = Depends(get_db),
):
    """노트 목록 — 제목·수정일·미리보기 1줄."""
    try:
        notes = await NoteService(db).list_notes(user_id)
        return {"success": True, "notes": notes}
    except Exception as e:
        logger.error(f"노트 목록 조회 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"노트 목록 조회 실패: {str(e)}")


@router.get("/notes/{note_id}")
async def get_note(
    note_id: int,
    user_id: str = Depends(get_authenticated_user_id),
    db: AsyncSession = Depends(get_db),
):
    """노트 상세 — 본문 + 백링크."""
    try:
        note = await NoteService(db).get_note(user_id, note_id)
    except Exception as e:
        logger.error(f"노트 조회 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"노트 조회 실패: {str(e)}")
    if note is None:
        raise HTTPException(status_code=404, detail="노트를 찾을 수 없습니다.")
    return {"success": True, "note": note}


@router.post("/notes")
async def create_note(
    request: NoteCreateRequest,
    user_id: str = Depends(get_authenticated_user_id),
    db: AsyncSession = Depends(get_db),
):
    """노트 생성 — 저장 시 [[링크]] 파싱."""
    try:
        note = await NoteService(db).create_note(
            user_id, request.title, request.content, request.taskId, request.questKey
        )
        return {"success": True, "note": note}
    except ValueError:
        raise HTTPException(status_code=409, detail="같은 제목의 노트가 이미 있습니다.")
    except Exception as e:
        logger.error(f"노트 생성 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"노트 생성 실패: {str(e)}")


@router.put("/notes/{note_id}")
async def update_note(
    note_id: int,
    request: NoteUpdateRequest,
    user_id: str = Depends(get_authenticated_user_id),
    db: AsyncSession = Depends(get_db),
):
    """노트 저장 — [[링크]] 재파싱."""
    raw = request.model_dump(exclude_unset=True)
    fields = {
        k_snake: raw[k_camel]
        for k_camel, k_snake in [
            ("title", "title"), ("content", "content"),
            ("taskId", "task_id"), ("questKey", "quest_key"),
        ]
        if k_camel in raw
    }
    try:
        note = await NoteService(db).update_note(user_id, note_id, fields)
    except ValueError:
        raise HTTPException(status_code=409, detail="같은 제목의 노트가 이미 있습니다.")
    except Exception as e:
        logger.error(f"노트 저장 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"노트 저장 실패: {str(e)}")
    if note is None:
        raise HTTPException(status_code=404, detail="노트를 찾을 수 없습니다.")
    return {"success": True, "note": note}


@router.delete("/notes/{note_id}")
async def delete_note(
    note_id: int,
    user_id: str = Depends(get_authenticated_user_id),
    db: AsyncSession = Depends(get_db),
):
    """노트 삭제."""
    try:
        ok = await NoteService(db).delete_note(user_id, note_id)
    except Exception as e:
        logger.error(f"노트 삭제 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"노트 삭제 실패: {str(e)}")
    if not ok:
        raise HTTPException(status_code=404, detail="노트를 찾을 수 없습니다.")
    return {"success": True}
```

- [ ] **Step 2: 앱 로드 스모크 확인** (라우팅·import 오류 검출)

Run (backend/ 에서): `python -c "from main import app; print(len([r for r in app.routes if r.path.startswith('/api/roadmap')]))"`
Expected: 숫자 출력(기존 4 + 신규 14 = 18), 예외 없음.

- [ ] **Step 3: 전체 백엔드 테스트 재실행**

Run: `python scripts/planner_decompose_parse_test.py; python scripts/planner_service_test.py; python scripts/roadmap_note_links_test.py; python scripts/roadmap_planner_parse_test.py`
Expected: 모두 FAIL 0

- [ ] **Step 4: 커밋**

```powershell
git add backend/api/v1/roadmap/roadmap_routor.py
git commit -m "feat(roadmap): 플래너·노트 API 14종 라우터 확장"
```

---

### Task 6: 프론트 기반 — 의존성·API 클라이언트·훅·목업

**Files:**
- Modify: `www.yeotaeho.kr/package.json` (pnpm add)
- Create: `www.yeotaeho.kr/src/lib/api/planner.ts`
- Create: `www.yeotaeho.kr/src/lib/api/notes.ts`
- Create: `www.yeotaeho.kr/src/hooks/usePlanner.ts`
- Create: `www.yeotaeho.kr/src/hooks/useNotes.ts`
- Create: `www.yeotaeho.kr/src/data/plannerMock.ts`

**Interfaces:**
- Consumes: Task 5 API 응답 스키마 (camelCase).
- Produces: 타입 `Sprint`, `PlannerTask`, `PlannerBoard`, `NoteListItem`, `NoteDetail` — Task 7~10 컴포넌트가 사용. 훅 `usePlannerBoard(enabled)`, `useCreateSprint()`, `usePatchSprint()`, `useDeleteSprint()`, `useCreateTask()`, `usePatchTask()`, `useDeleteTask()`, `useReorderTasks()`, `useDecomposeQuest()`, `useNotesList(enabled)`, `useNote(id)`, `useCreateNote()`, `useUpdateNote()`, `useDeleteNote()`.

- [ ] **Step 1: 의존성 설치** (www.yeotaeho.kr/ 에서)

```powershell
pnpm add @dnd-kit/core @dnd-kit/sortable react-markdown
```

Expected: React 19 peer 경고 없이 설치 완료 (경고가 나오면 버전 기록 후 진행 — dnd-kit core 6.x·sortable 10.x·react-markdown 10.x는 React 19 지원).

- [ ] **Step 2: API 클라이언트 작성**

`www.yeotaeho.kr/src/lib/api/planner.ts`:

```typescript
// 플래너(WBS) 백엔드 API 클라이언트 — 보드·스프린트·태스크·AI 분해
import { apiClient } from './client';

export type SprintState = 'planned' | 'active' | 'done';
export type TaskStatus = 'todo' | 'doing' | 'done';

export interface Sprint {
  id: number;
  title: string;
  goal: string | null;
  startDate: string;
  endDate: string;
  state: SprintState;
  position: number;
}

export interface PlannerTask {
  id: number;
  sprintId: number | null; // null = 백로그
  questKey: string | null;
  title: string;
  description: string;
  status: TaskStatus;
  startDate: string | null;
  dueDate: string | null;
  estimatedDays: number | null;
  position: number;
  source: 'user' | 'ai';
}

export interface PlannerBoard {
  sprints: Sprint[];
  tasks: PlannerTask[];
}

export async function fetchPlannerBoard(): Promise<PlannerBoard> {
  const { data } = await apiClient.get('/api/roadmap/planner');
  return { sprints: data?.sprints ?? [], tasks: data?.tasks ?? [] };
}

export interface SprintCreatePayload {
  title: string;
  goal?: string | null;
  startDate: string;
  endDate: string;
}

export async function createSprint(payload: SprintCreatePayload): Promise<Sprint> {
  const { data } = await apiClient.post('/api/roadmap/planner/sprints', payload);
  return data.sprint as Sprint;
}

export type SprintPatchPayload = Partial<
  Pick<Sprint, 'title' | 'goal' | 'startDate' | 'endDate' | 'state' | 'position'>
>;

export async function patchSprint(id: number, payload: SprintPatchPayload): Promise<void> {
  await apiClient.patch(`/api/roadmap/planner/sprints/${id}`, payload);
}

export async function deleteSprint(id: number): Promise<void> {
  await apiClient.delete(`/api/roadmap/planner/sprints/${id}`);
}

export interface TaskCreatePayload {
  title: string;
  description?: string | null;
  sprintId?: number | null;
  questKey?: string | null;
  startDate?: string | null;
  dueDate?: string | null;
  estimatedDays?: number | null;
}

export async function createTask(payload: TaskCreatePayload): Promise<PlannerTask> {
  const { data } = await apiClient.post('/api/roadmap/planner/tasks', payload);
  return data.task as PlannerTask;
}

export type TaskPatchPayload = Partial<
  Pick<
    PlannerTask,
    | 'title' | 'description' | 'sprintId' | 'questKey' | 'status'
    | 'startDate' | 'dueDate' | 'estimatedDays' | 'position'
  >
>;

export async function patchTask(id: number, payload: TaskPatchPayload): Promise<void> {
  await apiClient.patch(`/api/roadmap/planner/tasks/${id}`, payload);
}

export async function deleteTask(id: number): Promise<void> {
  await apiClient.delete(`/api/roadmap/planner/tasks/${id}`);
}

export async function reorderTasks(
  sprintId: number | null,
  taskIds: number[],
): Promise<void> {
  await apiClient.post('/api/roadmap/planner/tasks/reorder', { sprintId, taskIds });
}

export interface DecomposeResult {
  source: 'llm' | 'template';
  tasks: PlannerTask[];
}

export async function decomposeQuest(questKey: string): Promise<DecomposeResult> {
  const { data } = await apiClient.post('/api/roadmap/planner/decompose', { questKey });
  return { source: data?.source ?? 'template', tasks: data?.tasks ?? [] };
}
```

`www.yeotaeho.kr/src/lib/api/notes.ts`:

```typescript
// 로드맵 노트 백엔드 API 클라이언트 — 목록·상세(백링크)·CRUD
import { apiClient } from './client';

export interface NoteListItem {
  id: number;
  title: string;
  updatedAt: string | null;
  preview: string;
}

export interface NoteDetail {
  id: number;
  title: string;
  content: string;
  linkedTitles: string[];
  taskId: number | null;
  questKey: string | null;
  updatedAt: string | null;
  backlinks: { id: number; title: string }[];
}

export async function fetchNotes(): Promise<NoteListItem[]> {
  const { data } = await apiClient.get('/api/roadmap/notes');
  return data?.notes ?? [];
}

export async function fetchNote(id: number): Promise<NoteDetail> {
  const { data } = await apiClient.get(`/api/roadmap/notes/${id}`);
  return data.note as NoteDetail;
}

export interface NotePayload {
  title?: string;
  content?: string;
  taskId?: number | null;
  questKey?: string | null;
}

export async function createNote(payload: NotePayload & { title: string }): Promise<NoteDetail> {
  const { data } = await apiClient.post('/api/roadmap/notes', payload);
  return data.note as NoteDetail;
}

export async function updateNote(id: number, payload: NotePayload): Promise<NoteDetail> {
  const { data } = await apiClient.put(`/api/roadmap/notes/${id}`, payload);
  return data.note as NoteDetail;
}

export async function deleteNote(id: number): Promise<void> {
  await apiClient.delete(`/api/roadmap/notes/${id}`);
}
```

- [ ] **Step 3: TanStack Query 훅 작성**

`www.yeotaeho.kr/src/hooks/usePlanner.ts`:

```typescript
// 플래너 라이브 데이터 TanStack Query 훅 — 보드·스프린트·태스크·분해
'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  createSprint,
  createTask,
  decomposeQuest,
  deleteSprint,
  deleteTask,
  fetchPlannerBoard,
  patchSprint,
  patchTask,
  reorderTasks,
  SprintCreatePayload,
  SprintPatchPayload,
  TaskCreatePayload,
  TaskPatchPayload,
} from '@/lib/api/planner';

const KEY = ['roadmap-planner'];
const STALE = 60 * 1000; // 1분 — 편집 빈도가 높은 화면

export function usePlannerBoard(enabled = true) {
  return useQuery({
    queryKey: KEY,
    queryFn: fetchPlannerBoard,
    enabled,
    staleTime: STALE,
    retry: 1,
  });
}

function useInvalidateBoard() {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ queryKey: KEY });
}

export function useCreateSprint() {
  const invalidate = useInvalidateBoard();
  return useMutation({
    mutationFn: (payload: SprintCreatePayload) => createSprint(payload),
    onSuccess: invalidate,
  });
}

export function usePatchSprint() {
  const invalidate = useInvalidateBoard();
  return useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: SprintPatchPayload }) =>
      patchSprint(id, payload),
    onSuccess: invalidate,
  });
}

export function useDeleteSprint() {
  const invalidate = useInvalidateBoard();
  return useMutation({
    mutationFn: (id: number) => deleteSprint(id),
    onSuccess: invalidate,
  });
}

export function useCreateTask() {
  const invalidate = useInvalidateBoard();
  return useMutation({
    mutationFn: (payload: TaskCreatePayload) => createTask(payload),
    onSuccess: invalidate,
  });
}

export function usePatchTask() {
  const invalidate = useInvalidateBoard();
  return useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: TaskPatchPayload }) =>
      patchTask(id, payload),
    onSuccess: invalidate,
  });
}

export function useDeleteTask() {
  const invalidate = useInvalidateBoard();
  return useMutation({
    mutationFn: (id: number) => deleteTask(id),
    onSuccess: invalidate,
  });
}

export function useReorderTasks() {
  const invalidate = useInvalidateBoard();
  return useMutation({
    mutationFn: ({ sprintId, taskIds }: { sprintId: number | null; taskIds: number[] }) =>
      reorderTasks(sprintId, taskIds),
    // 드래그는 로컬 state 선반영(BoardView) — 실패 시에만 서버 재동기화
    onError: invalidate,
  });
}

export function useDecomposeQuest() {
  const invalidate = useInvalidateBoard();
  return useMutation({
    mutationFn: (questKey: string) => decomposeQuest(questKey),
    onSuccess: invalidate,
  });
}
```

`www.yeotaeho.kr/src/hooks/useNotes.ts`:

```typescript
// 노트 라이브 데이터 TanStack Query 훅 — 목록·상세·CRUD
'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  createNote,
  deleteNote,
  fetchNote,
  fetchNotes,
  NotePayload,
  updateNote,
} from '@/lib/api/notes';

const LIST_KEY = ['roadmap-notes'];

export function useNotesList(enabled = true) {
  return useQuery({
    queryKey: LIST_KEY,
    queryFn: fetchNotes,
    enabled,
    staleTime: 60 * 1000,
    retry: 1,
  });
}

export function useNote(id: number | null, enabled = true) {
  return useQuery({
    queryKey: ['roadmap-note', id],
    queryFn: () => fetchNote(id as number),
    enabled: enabled && id != null,
    staleTime: 30 * 1000,
    retry: 1,
  });
}

export function useCreateNote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: NotePayload & { title: string }) => createNote(payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: LIST_KEY }),
  });
}

export function useUpdateNote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: NotePayload }) =>
      updateNote(id, payload),
    onSuccess: (saved) => {
      qc.setQueryData(['roadmap-note', saved.id], saved);
      qc.invalidateQueries({ queryKey: LIST_KEY });
    },
  });
}

export function useDeleteNote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => deleteNote(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: LIST_KEY }),
  });
}
```

- [ ] **Step 4: 비로그인 목업 데이터 작성**

`www.yeotaeho.kr/src/data/plannerMock.ts`:

```typescript
/** 플래너·노트 비로그인 목업 — read-only 예시 데이터 (JourneyMap QUEST_TREE 와 questKey 정합) */

import type { PlannerBoard } from '@/lib/api/planner';
import type { NoteDetail, NoteListItem } from '@/lib/api/notes';

function isoOffset(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() + days);
  const p = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

export const PLANNER_MOCK: PlannerBoard = {
  sprints: [
    {
      id: 1, title: '이번 주 — 도메인 언어 익히기', goal: 'ESG 지표 지형도 완성',
      startDate: isoOffset(-1), endDate: isoOffset(5), state: 'active', position: 0,
    },
    {
      id: 2, title: '다음 주 — 스키마 초안', goal: null,
      startDate: isoOffset(6), endDate: isoOffset(12), state: 'planned', position: 1,
    },
  ],
  tasks: [
    { id: 11, sprintId: 1, questKey: 'q-esg-map', title: '공개 데이터 소스 목록화',
      description: '공공 API·리포트 소스 정리', status: 'done',
      startDate: isoOffset(-1), dueDate: isoOffset(1), estimatedDays: 2, position: 0, source: 'ai' },
    { id: 12, sprintId: 1, questKey: 'q-esg-map', title: '지표 용어집 초안',
      description: '핵심 지표 20개 한 장 정리', status: 'doing',
      startDate: isoOffset(1), dueDate: isoOffset(4), estimatedDays: 3, position: 1, source: 'ai' },
    { id: 13, sprintId: 2, questKey: 'q-carbon-schema', title: '탄소 데이터 엔티티 도출',
      description: '배출·감축 흐름 스케치', status: 'todo',
      startDate: isoOffset(6), dueDate: isoOffset(9), estimatedDays: 4, position: 0, source: 'user' },
    { id: 14, sprintId: null, questKey: 'q-pipeline-mini', title: 'FastAPI 미니 파이프라인 조사',
      description: '', status: 'todo',
      startDate: null, dueDate: null, estimatedDays: 5, position: 0, source: 'ai' },
    { id: 15, sprintId: null, questKey: null, title: '주간 회고 쓰기',
      description: '', status: 'todo',
      startDate: null, dueDate: null, estimatedDays: 1, position: 1, source: 'user' },
  ],
};

export const NOTES_MOCK_LIST: NoteListItem[] = [
  { id: 1, title: '탄소 스키마 아이디어', updatedAt: null, preview: 'scope3 경계를 어디서 끊을지 — [[지표 용어집]] 참고' },
  { id: 2, title: '지표 용어집', updatedAt: null, preview: 'Scope1/2/3, CSRD, 배출계수…' },
];

export const NOTES_MOCK_DETAIL: Record<number, NoteDetail> = {
  1: {
    id: 1, title: '탄소 스키마 아이디어',
    content: '## 경계 문제\n\nscope3 경계를 어디서 끊을지 고민. 자세한 용어는 [[지표 용어집]] 참고.\n\n- 엔티티: 배출원, 감축활동\n- 다음 행동: 미니 파이프라인과 연결',
    linkedTitles: ['지표 용어집'], taskId: null, questKey: 'q-carbon-schema',
    updatedAt: null, backlinks: [],
  },
  2: {
    id: 2, title: '지표 용어집',
    content: '# 용어집\n\n- **Scope1/2/3** — 직접·간접·가치사슬 배출\n- **CSRD** — EU 지속가능성 공시 지침',
    linkedTitles: [], taskId: null, questKey: 'q-esg-map',
    updatedAt: null, backlinks: [{ id: 1, title: '탄소 스키마 아이디어' }],
  },
};
```

- [ ] **Step 5: 린트 확인**

Run (www.yeotaeho.kr/ 에서): `pnpm lint`
Expected: 에러 0 (기존 워닝 외 신규 없음)

- [ ] **Step 6: 커밋**

```powershell
git add www.yeotaeho.kr/package.json www.yeotaeho.kr/pnpm-lock.yaml www.yeotaeho.kr/src/lib/api/planner.ts www.yeotaeho.kr/src/lib/api/notes.ts www.yeotaeho.kr/src/hooks/usePlanner.ts www.yeotaeho.kr/src/hooks/useNotes.ts www.yeotaeho.kr/src/data/plannerMock.ts
git commit -m "feat(roadmap-fe): 플래너·노트 API 클라이언트·훅·목업 + dnd-kit/react-markdown 도입"
```

---

### Task 7: 플래너 보드 뷰 + 탭 배선

**Files:**
- Create: `www.yeotaeho.kr/src/components/features/roadmap/planner/PlannerTab.tsx`
- Create: `www.yeotaeho.kr/src/components/features/roadmap/planner/BoardView.tsx`
- Create: `www.yeotaeho.kr/src/components/features/roadmap/planner/TaskCard.tsx`
- Modify: `www.yeotaeho.kr/src/components/features/roadmap/RoadmapNavContext.tsx:7` (`RoadmapSubTab`에 `"planner" | "notes"` 추가)
- Modify: `www.yeotaeho.kr/src/components/features/roadmap/RoadmapSidebar.tsx:9-12` (탭 배열에 planner·notes 추가)
- Modify: `www.yeotaeho.kr/src/components/features/roadmap/RoadmapView.tsx:24` (subTab 분기 확장)

**Interfaces:**
- Consumes: Task 6 훅·타입·목업.
- Produces: `PlannerTab`(뷰 토글 shell — Task 8이 타임라인 분기 추가), `BoardView({board, readOnly, onMoved})`, `TaskCard({task, questTitle})`. `TimelineView`는 Task 8에서 추가하므로 이 시점 토글은 보드만 노출.

- [ ] **Step 1: 탭 배선 수정** — 3개 파일:

`RoadmapNavContext.tsx` 7행:

```typescript
export type RoadmapSubTab = "journey" | "planner" | "notes" | "archive";
```

`RoadmapSidebar.tsx` — import에 `KanbanSquare, NotebookPen` 추가, 배열 교체:

```typescript
import { CalendarDays, KanbanSquare, Map, NotebookPen, type LucideIcon } from "lucide-react";
```

```typescript
const ROADMAP_TABS: { id: RoadmapSubTab; label: string; icon: LucideIcon }[] = [
  { id: "journey", label: "여정 개요", icon: Map },
  { id: "planner", label: "플래너", icon: KanbanSquare },
  { id: "notes", label: "노트", icon: NotebookPen },
  { id: "archive", label: "성장 아카이브", icon: CalendarDays },
];
```

`RoadmapView.tsx` — import 2줄 추가 후 24행 분기 교체:

```typescript
import { NotesTab } from "./notes/NotesTab";
import { PlannerTab } from "./planner/PlannerTab";
```

```tsx
          {subTab === "journey" ? (
            <JourneyMapTab />
          ) : subTab === "planner" ? (
            <PlannerTab />
          ) : subTab === "notes" ? (
            <NotesTab />
          ) : (
            <GrowthArchiveTab />
          )}
```

주의: `NotesTab`은 Task 9에서 작성한다. 이 태스크의 빌드가 깨지지 않도록 **Task 7에서는 `NotesTab` import·분기를 넣지 않고** planner 분기까지만 추가한다 (notes 분기는 Task 9에서 추가).

- [ ] **Step 2: TaskCard 작성**

`www.yeotaeho.kr/src/components/features/roadmap/planner/TaskCard.tsx`:

```tsx
"use client";

// 플래너 태스크 카드 — 보드·백로그 공용 (퀘스트 칩·AI 배지·기간)

import { Bot, CalendarRange } from "lucide-react";
import type { PlannerTask } from "@/lib/api/planner";

const STATUS_STYLE: Record<string, string> = {
  todo: "border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-800",
  doing:
    "border-indigo-300 bg-indigo-50/60 ring-1 ring-indigo-200/60 dark:border-indigo-700 dark:bg-indigo-900/20 dark:ring-indigo-900/40",
  done: "border-emerald-200 bg-emerald-50/40 opacity-80 dark:border-emerald-900/40 dark:bg-emerald-900/10",
};

export function TaskCard({
  task,
  questTitle,
  onClick,
}: {
  task: PlannerTask;
  questTitle?: string;
  onClick?: () => void;
}) {
  return (
    <div
      onClick={onClick}
      className={`cursor-grab rounded-xl border p-3 shadow-sm transition hover:shadow-md active:cursor-grabbing ${
        STATUS_STYLE[task.status] ?? STATUS_STYLE.todo
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <p
          className={`text-xs font-semibold text-slate-900 dark:text-slate-100 ${
            task.status === "done" ? "line-through" : ""
          }`}
        >
          {task.title}
        </p>
        {task.source === "ai" ? (
          <span className="inline-flex shrink-0 items-center gap-0.5 rounded-full bg-violet-100 px-1.5 py-0.5 text-[9px] font-bold text-violet-700 dark:bg-violet-900/35 dark:text-violet-300">
            <Bot className="h-2.5 w-2.5" />
            AI
          </span>
        ) : null}
      </div>
      {task.description ? (
        <p className="mt-1 line-clamp-2 text-[11px] text-slate-600 dark:text-slate-400">
          {task.description}
        </p>
      ) : null}
      <div className="mt-2 flex flex-wrap items-center gap-1.5">
        {questTitle ? (
          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-600 dark:bg-slate-700 dark:text-slate-300">
            🗺 {questTitle}
          </span>
        ) : null}
        {task.dueDate ? (
          <span className="inline-flex items-center gap-0.5 rounded-full bg-sky-50 px-2 py-0.5 text-[10px] font-medium text-sky-700 dark:bg-sky-900/25 dark:text-sky-300">
            <CalendarRange className="h-2.5 w-2.5" />
            ~{task.dueDate.slice(5).replace("-", "/")}
          </span>
        ) : task.estimatedDays ? (
          <span className="rounded-full bg-slate-50 px-2 py-0.5 text-[10px] text-slate-500 dark:bg-slate-900 dark:text-slate-400">
            약 {task.estimatedDays}일
          </span>
        ) : null}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: BoardView 작성** — dnd-kit 컬럼 보드.

`www.yeotaeho.kr/src/components/features/roadmap/planner/BoardView.tsx`:

```tsx
"use client";

// 플래너 보드 뷰 — 백로그 + 스프린트 컬럼, dnd-kit 드래그 이동·정렬

import {
  DndContext,
  DragEndEvent,
  DragOverlay,
  DragStartEvent,
  PointerSensor,
  closestCorners,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import {
  SortableContext,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { Inbox, Plus, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";
import type { PlannerBoard, PlannerTask, Sprint } from "@/lib/api/planner";
import { TaskCard } from "./TaskCard";

// 컬럼 id 규약: 백로그 "backlog", 스프린트 "sprint-<id>"
const BACKLOG = "backlog";
const colId = (sprintId: number | null) => (sprintId == null ? BACKLOG : `sprint-${sprintId}`);
const parseCol = (id: string): number | null =>
  id === BACKLOG ? null : Number(id.replace("sprint-", ""));

function SortableTask({
  task,
  questTitle,
  disabled,
  onClick,
}: {
  task: PlannerTask;
  questTitle?: string;
  disabled: boolean;
  onClick?: () => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: String(task.id),
    disabled,
  });
  return (
    <div
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      className={isDragging ? "opacity-40" : ""}
      {...attributes}
      {...listeners}
    >
      <TaskCard task={task} questTitle={questTitle} onClick={onClick} />
    </div>
  );
}

function Column({
  id,
  title,
  subtitle,
  tasks,
  questTitles,
  readOnly,
  onAddTask,
  onDeleteSprint,
  onTaskClick,
  progress,
}: {
  id: string;
  title: string;
  subtitle?: string;
  tasks: PlannerTask[];
  questTitles: Map<string, string>;
  readOnly: boolean;
  onAddTask?: () => void;
  onDeleteSprint?: () => void;
  onTaskClick?: (t: PlannerTask) => void;
  progress?: number; // 0~100
}) {
  return (
    <section className="flex w-72 shrink-0 flex-col rounded-2xl border border-slate-200 bg-[#F8FAFC] p-3 shadow-sm dark:border-slate-700 dark:bg-slate-900">
      <div className="flex items-start justify-between gap-2 px-1">
        <div>
          <h3 className="text-xs font-bold text-slate-900 dark:text-slate-100">{title}</h3>
          {subtitle ? (
            <p className="mt-0.5 text-[10px] text-slate-500 dark:text-slate-500">{subtitle}</p>
          ) : null}
        </div>
        <div className="flex items-center gap-1">
          {onAddTask ? (
            <button
              type="button"
              onClick={onAddTask}
              className="rounded-lg border border-slate-200 p-1 text-slate-500 hover:bg-white dark:border-slate-700 dark:text-slate-400 dark:hover:bg-slate-800"
              aria-label="태스크 추가"
            >
              <Plus className="h-3.5 w-3.5" />
            </button>
          ) : null}
          {onDeleteSprint ? (
            <button
              type="button"
              onClick={onDeleteSprint}
              className="rounded-lg border border-slate-200 p-1 text-slate-400 hover:bg-rose-50 hover:text-rose-600 dark:border-slate-700 dark:hover:bg-rose-900/20"
              aria-label="스프린트 삭제"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          ) : null}
        </div>
      </div>
      {progress != null ? (
        <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700">
          <div
            className="h-full rounded-full bg-indigo-500 transition-all"
            style={{ width: `${progress}%` }}
          />
        </div>
      ) : null}
      <SortableContext
        id={id}
        items={tasks.map((t) => String(t.id))}
        strategy={verticalListSortingStrategy}
      >
        <div className="mt-3 flex min-h-[80px] flex-1 flex-col gap-2" data-column={id}>
          {tasks.map((t) => (
            <SortableTask
              key={t.id}
              task={t}
              questTitle={t.questKey ? questTitles.get(t.questKey) : undefined}
              disabled={readOnly}
              onClick={() => onTaskClick?.(t)}
            />
          ))}
          {tasks.length === 0 ? (
            <p className="rounded-xl border border-dashed border-slate-200 p-4 text-center text-[11px] text-slate-400 dark:border-slate-700">
              카드를 끌어다 놓으세요
            </p>
          ) : null}
        </div>
      </SortableContext>
    </section>
  );
}

export function BoardView({
  board,
  questTitles,
  readOnly,
  onMove,
  onAddTask,
  onAddSprint,
  onDeleteSprint,
  onTaskClick,
}: {
  board: PlannerBoard;
  questTitles: Map<string, string>;
  readOnly: boolean;
  /** 드래그 확정 — 대상 컬럼(sprintId)과 그 컬럼의 새 taskId 순서 */
  onMove: (sprintId: number | null, taskIds: number[]) => void;
  onAddTask: (sprintId: number | null) => void;
  onAddSprint: () => void;
  onDeleteSprint: (id: number) => void;
  onTaskClick: (t: PlannerTask) => void;
}) {
  const [activeTask, setActiveTask] = useState<PlannerTask | null>(null);
  // 드래그 중 로컬 배치 상태 — 서버 확정 전 선반영
  const [local, setLocal] = useState<PlannerTask[] | null>(null);
  const tasks = local ?? board.tasks;

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }));

  const byColumn = useMemo(() => {
    const m = new Map<string, PlannerTask[]>();
    m.set(BACKLOG, []);
    for (const s of board.sprints) m.set(colId(s.id), []);
    for (const t of tasks) {
      const key = colId(t.sprintId);
      if (!m.has(key)) m.set(key, []);
      m.get(key)!.push(t);
    }
    for (const list of m.values()) list.sort((a, b) => a.position - b.position || a.id - b.id);
    return m;
  }, [tasks, board.sprints]);

  const findColumnOf = (taskId: string): string | undefined => {
    for (const [cid, list] of byColumn) {
      if (list.some((t) => String(t.id) === taskId)) return cid;
    }
    return undefined;
  };

  const handleDragStart = (e: DragStartEvent) => {
    const t = tasks.find((x) => String(x.id) === String(e.active.id));
    setActiveTask(t ?? null);
  };

  const handleDragEnd = (e: DragEndEvent) => {
    setActiveTask(null);
    const { active, over } = e;
    if (!over) return;
    const fromCol = findColumnOf(String(active.id));
    // over 가 태스크면 그 태스크의 컬럼, 컬럼 컨테이너면 그대로
    const overIsColumn = String(over.id) === BACKLOG || String(over.id).startsWith("sprint-");
    const toCol = overIsColumn ? String(over.id) : findColumnOf(String(over.id));
    if (!fromCol || !toCol) return;

    const moved = tasks.find((t) => String(t.id) === String(active.id));
    if (!moved) return;

    const target = (byColumn.get(toCol) ?? []).filter((t) => t.id !== moved.id);
    let insertAt = target.length;
    if (!overIsColumn) {
      const idx = target.findIndex((t) => String(t.id) === String(over.id));
      if (idx >= 0) insertAt = idx;
    }
    target.splice(insertAt, 0, { ...moved, sprintId: parseCol(toCol) });

    // 로컬 선반영: 대상 컬럼 position 재부여
    const targetIds = new Set(target.map((t) => t.id));
    setLocal(
      tasks
        .filter((t) => !targetIds.has(t.id))
        .concat(target.map((t, i) => ({ ...t, position: i }))),
    );
    onMove(parseCol(toCol), target.map((t) => t.id));
  };

  const doneRatio = (list: PlannerTask[]) =>
    list.length ? Math.round((list.filter((t) => t.status === "done").length / list.length) * 100) : 0;

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCorners}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
    >
      <div className="flex gap-4 overflow-x-auto pb-2">
        <Column
          id={BACKLOG}
          title="📥 백로그"
          subtitle="일정 미배정 태스크"
          tasks={byColumn.get(BACKLOG) ?? []}
          questTitles={questTitles}
          readOnly={readOnly}
          onAddTask={readOnly ? undefined : () => onAddTask(null)}
          onTaskClick={onTaskClick}
        />
        {board.sprints.map((s: Sprint) => {
          const list = byColumn.get(colId(s.id)) ?? [];
          return (
            <Column
              key={s.id}
              id={colId(s.id)}
              title={s.title}
              subtitle={`${s.startDate.slice(5)} ~ ${s.endDate.slice(5)}${s.goal ? ` · ${s.goal}` : ""}`}
              tasks={list}
              questTitles={questTitles}
              readOnly={readOnly}
              progress={doneRatio(list)}
              onAddTask={readOnly ? undefined : () => onAddTask(s.id)}
              onDeleteSprint={readOnly ? undefined : () => onDeleteSprint(s.id)}
              onTaskClick={onTaskClick}
            />
          );
        })}
        {!readOnly ? (
          <button
            type="button"
            onClick={onAddSprint}
            className="flex h-24 w-56 shrink-0 items-center justify-center gap-1.5 rounded-2xl border-2 border-dashed border-slate-200 text-sm font-semibold text-slate-400 transition hover:border-indigo-300 hover:text-indigo-600 dark:border-slate-700 dark:hover:border-indigo-700"
          >
            <Plus className="h-4 w-4" />
            스프린트 추가
          </button>
        ) : null}
        <div className="hidden">
          <Inbox className="h-4 w-4" />
        </div>
      </div>
      <DragOverlay>
        {activeTask ? (
          <TaskCard
            task={activeTask}
            questTitle={activeTask.questKey ? questTitles.get(activeTask.questKey) : undefined}
          />
        ) : null}
      </DragOverlay>
    </DndContext>
  );
}
```

- [ ] **Step 4: PlannerTab 작성** — 데이터 로드·목업 폴백·생성 폼·태스크 편집 패널.

`www.yeotaeho.kr/src/components/features/roadmap/planner/PlannerTab.tsx`:

```tsx
"use client";

// 플래너 탭 — 보드/타임라인 토글 셸 + 데이터 로드·목업 폴백·생성/편집 다이얼로그

import { KanbanSquare, X } from "lucide-react";
import { useMemo, useState } from "react";
import { PLANNER_MOCK } from "@/data/plannerMock";
import { flattenQuestTitles, QUEST_TREE } from "@/data/roadmapQuestMap";
import { useJourney } from "@/hooks/useRoadmap";
import {
  useCreateSprint,
  useCreateTask,
  useDeleteSprint,
  useDeleteTask,
  usePatchTask,
  usePlannerBoard,
  useReorderTasks,
} from "@/hooks/usePlanner";
import type { PlannerTask, TaskStatus } from "@/lib/api/planner";
import { useStore } from "@/store";
import { BoardView } from "./BoardView";

type PlannerView = "board" | "timeline";

function isoToday(offset = 0): string {
  const d = new Date();
  d.setDate(d.getDate() + offset);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

export function PlannerTab() {
  const profile = useStore((s) => s.profile);
  const enabled = !!profile?.id;
  const { data, isLoading } = usePlannerBoard(enabled);
  const { data: journey } = useJourney(enabled);
  const board = enabled && data ? data : PLANNER_MOCK;
  const isLive = enabled && Boolean(data);

  const [view, setView] = useState<PlannerView>("board");
  const [editing, setEditing] = useState<PlannerTask | null>(null);
  const [addingTo, setAddingTo] = useState<{ open: boolean; sprintId: number | null }>({
    open: false,
    sprintId: null,
  });
  const [addingSprint, setAddingSprint] = useState(false);

  const questTitles = useMemo(() => {
    const tree = journey?.questTree ?? QUEST_TREE;
    return new Map(flattenQuestTitles(tree).map((q) => [q.id, q.title]));
  }, [journey]);

  const createSprint = useCreateSprint();
  const deleteSprint = useDeleteSprint();
  const createTask = useCreateTask();
  const patchTask = usePatchTask();
  const deleteTask = useDeleteTask();
  const reorder = useReorderTasks();

  const handleMove = (sprintId: number | null, taskIds: number[]) => {
    if (!enabled) return;
    reorder.mutate({ sprintId, taskIds });
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="inline-flex items-center gap-2 text-lg font-bold text-slate-900 dark:text-slate-100">
            <KanbanSquare className="h-5 w-5 text-indigo-600" />
            플래너
          </h2>
          <p className="mt-0.5 text-xs text-slate-600 dark:text-slate-400">
            퀘스트를 실행 태스크로 쪼개고, 스프린트로 묶어 일정을 잡습니다.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {!isLive && !isLoading ? (
            <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-500 dark:bg-slate-800 dark:text-slate-400">
              예시 데이터
            </span>
          ) : null}
          <div className="flex rounded-xl border border-slate-200 p-0.5 dark:border-slate-700">
            {(["board", "timeline"] as const).map((v) => (
              <button
                key={v}
                type="button"
                onClick={() => setView(v)}
                className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                  view === v
                    ? "bg-indigo-600 text-white shadow-sm"
                    : "text-slate-600 hover:text-indigo-600 dark:text-slate-400"
                }`}
              >
                {v === "board" ? "보드" : "타임라인"}
              </button>
            ))}
          </div>
        </div>
      </div>

      {view === "board" ? (
        <BoardView
          board={board}
          questTitles={questTitles}
          readOnly={!enabled}
          onMove={handleMove}
          onAddTask={(sprintId) => setAddingTo({ open: true, sprintId })}
          onAddSprint={() => setAddingSprint(true)}
          onDeleteSprint={(id) => {
            if (window.confirm("스프린트를 삭제할까요? 소속 태스크는 백로그로 돌아갑니다.")) {
              deleteSprint.mutate(id);
            }
          }}
          onTaskClick={(t) => setEditing(t)}
        />
      ) : (
        <p className="rounded-2xl border border-dashed border-slate-200 p-8 text-center text-sm text-slate-400 dark:border-slate-700">
          타임라인 뷰는 다음 단계에서 열립니다.
        </p>
      )}

      {/* 태스크 추가 폼 */}
      {addingTo.open ? (
        <TaskForm
          title="태스크 추가"
          onClose={() => setAddingTo({ open: false, sprintId: null })}
          onSubmit={(v) => {
            createTask.mutate({ ...v, sprintId: addingTo.sprintId });
            setAddingTo({ open: false, sprintId: null });
          }}
        />
      ) : null}

      {/* 스프린트 추가 폼 */}
      {addingSprint ? (
        <SprintForm
          onClose={() => setAddingSprint(false)}
          onSubmit={(v) => {
            createSprint.mutate(v);
            setAddingSprint(false);
          }}
        />
      ) : null}

      {/* 태스크 편집 패널 */}
      {editing ? (
        <TaskEditPanel
          task={editing}
          readOnly={!enabled}
          onClose={() => setEditing(null)}
          onSave={(fields) => {
            patchTask.mutate({ id: editing.id, payload: fields });
            setEditing(null);
          }}
          onDelete={() => {
            if (window.confirm("태스크를 삭제할까요?")) {
              deleteTask.mutate(editing.id);
              setEditing(null);
            }
          }}
        />
      ) : null}
    </div>
  );
}

function Modal({ children, onClose }: { children: React.ReactNode; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4">
      <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-5 shadow-xl dark:border-slate-700 dark:bg-slate-800">
        <div className="flex justify-end">
          <button type="button" onClick={onClose} aria-label="닫기">
            <X className="h-4 w-4 text-slate-400 hover:text-slate-600" />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

const inputCls =
  "mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 focus:border-indigo-300 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100";
const labelCls = "block text-xs font-semibold text-slate-600 dark:text-slate-400";
const primaryBtnCls =
  "mt-4 w-full rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-indigo-700 disabled:opacity-60";

function TaskForm({
  title,
  onClose,
  onSubmit,
}: {
  title: string;
  onClose: () => void;
  onSubmit: (v: { title: string; description: string }) => void;
}) {
  const [name, setName] = useState("");
  const [desc, setDesc] = useState("");
  return (
    <Modal onClose={onClose}>
      <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">{title}</h3>
      <label className={`${labelCls} mt-3`}>
        제목
        <input value={name} onChange={(e) => setName(e.target.value)} className={inputCls} />
      </label>
      <label className={`${labelCls} mt-3`}>
        설명 (선택)
        <textarea value={desc} onChange={(e) => setDesc(e.target.value)} rows={3} className={inputCls} />
      </label>
      <button
        type="button"
        disabled={!name.trim()}
        onClick={() => onSubmit({ title: name.trim(), description: desc.trim() })}
        className={primaryBtnCls}
      >
        추가
      </button>
    </Modal>
  );
}

function SprintForm({
  onClose,
  onSubmit,
}: {
  onClose: () => void;
  onSubmit: (v: { title: string; goal: string | null; startDate: string; endDate: string }) => void;
}) {
  const [name, setName] = useState("");
  const [goal, setGoal] = useState("");
  const [start, setStart] = useState(isoToday());
  const [end, setEnd] = useState(isoToday(6));
  const valid = name.trim().length > 0 && start <= end;
  return (
    <Modal onClose={onClose}>
      <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">스프린트 추가</h3>
      <label className={`${labelCls} mt-3`}>
        제목
        <input value={name} onChange={(e) => setName(e.target.value)} className={inputCls} placeholder="예: 1주차 — CS 기초" />
      </label>
      <label className={`${labelCls} mt-3`}>
        목표 (선택)
        <input value={goal} onChange={(e) => setGoal(e.target.value)} className={inputCls} />
      </label>
      <div className="mt-3 grid grid-cols-2 gap-2">
        <label className={labelCls}>
          시작일
          <input type="date" value={start} onChange={(e) => setStart(e.target.value)} className={inputCls} />
        </label>
        <label className={labelCls}>
          종료일
          <input type="date" value={end} onChange={(e) => setEnd(e.target.value)} className={inputCls} />
        </label>
      </div>
      <button
        type="button"
        disabled={!valid}
        onClick={() => onSubmit({ title: name.trim(), goal: goal.trim() || null, startDate: start, endDate: end })}
        className={primaryBtnCls}
      >
        추가
      </button>
    </Modal>
  );
}

function TaskEditPanel({
  task,
  readOnly,
  onClose,
  onSave,
  onDelete,
}: {
  task: PlannerTask;
  readOnly: boolean;
  onClose: () => void;
  onSave: (fields: { status: TaskStatus; startDate: string | null; dueDate: string | null }) => void;
  onDelete: () => void;
}) {
  const [status, setStatus] = useState<TaskStatus>(task.status);
  const [start, setStart] = useState(task.startDate ?? "");
  const [due, setDue] = useState(task.dueDate ?? "");
  return (
    <Modal onClose={onClose}>
      <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">{task.title}</h3>
      {task.description ? (
        <p className="mt-1 text-xs text-slate-600 dark:text-slate-400">{task.description}</p>
      ) : null}
      <label className={`${labelCls} mt-3`}>
        상태
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value as TaskStatus)}
          className={inputCls}
          disabled={readOnly}
        >
          <option value="todo">할 일</option>
          <option value="doing">진행 중</option>
          <option value="done">완료</option>
        </select>
      </label>
      <div className="mt-3 grid grid-cols-2 gap-2">
        <label className={labelCls}>
          시작일
          <input type="date" value={start} onChange={(e) => setStart(e.target.value)} className={inputCls} disabled={readOnly} />
        </label>
        <label className={labelCls}>
          마감일
          <input type="date" value={due} onChange={(e) => setDue(e.target.value)} className={inputCls} disabled={readOnly} />
        </label>
      </div>
      {!readOnly ? (
        <>
          <button
            type="button"
            onClick={() => onSave({ status, startDate: start || null, dueDate: due || null })}
            className={primaryBtnCls}
          >
            저장
          </button>
          <button
            type="button"
            onClick={onDelete}
            className="mt-2 w-full rounded-xl border border-rose-200 px-4 py-2 text-xs font-semibold text-rose-600 hover:bg-rose-50 dark:border-rose-900/40 dark:hover:bg-rose-900/15"
          >
            태스크 삭제
          </button>
        </>
      ) : (
        <p className="mt-4 text-center text-xs text-slate-400">로그인하면 편집할 수 있습니다.</p>
      )}
    </Modal>
  );
}
```

- [ ] **Step 5: 빌드·라이브 확인**

Run: `pnpm lint` → 에러 0. `pnpm build` → 성공.
Claude Preview로 dev 서버 기동 후 `/roadmap` 접속: 플래너 탭 노출, 목업 보드 렌더(백로그 + 스프린트 2컬럼), 카드 드래그 시 비로그인 read-only(이동 없음) 확인. 콘솔 에러 0.

- [ ] **Step 6: 커밋**

```powershell
git add www.yeotaeho.kr/src/components/features/roadmap/planner/ www.yeotaeho.kr/src/components/features/roadmap/RoadmapNavContext.tsx www.yeotaeho.kr/src/components/features/roadmap/RoadmapSidebar.tsx www.yeotaeho.kr/src/components/features/roadmap/RoadmapView.tsx
git commit -m "feat(roadmap-fe): 플래너 탭 보드 뷰 — 백로그·스프린트 컬럼·dnd-kit 드래그"
```

---

### Task 8: 주간 타임라인(간트) 뷰

**Files:**
- Create: `www.yeotaeho.kr/src/components/features/roadmap/planner/TimelineView.tsx`
- Modify: `www.yeotaeho.kr/src/components/features/roadmap/planner/PlannerTab.tsx` (플레이스홀더 분기 → TimelineView)

**Interfaces:**
- Consumes: Task 6 타입, Task 7 `PlannerTab` 셸·`TaskEditPanel`(bar 클릭 시 동일 편집 패널 재사용 — `onTaskClick` 전달).
- Produces: `TimelineView({board, onTaskClick})` — read-only 여부는 편집 패널(TaskEditPanel)이 이미 처리하므로 prop 불필요.

- [ ] **Step 1: TimelineView 작성**

`www.yeotaeho.kr/src/components/features/roadmap/planner/TimelineView.tsx`:

```tsx
"use client";

// 플래너 주간 타임라인(간트) 뷰 — CSS Grid 7열, 태스크 기간 bar·스프린트 음영 밴드

import { CalendarClock, ChevronLeft, ChevronRight } from "lucide-react";
import { useMemo, useState } from "react";
import type { PlannerBoard, PlannerTask } from "@/lib/api/planner";

const DAY_MS = 24 * 60 * 60 * 1000;
const WEEK_LABELS = ["일", "월", "화", "수", "목", "금", "토"];

// 스프린트별 순환 pastel 팔레트 — 라이트 100번대 / 다크 900번대
const BAR_PALETTE = [
  "bg-sky-100 text-sky-900 border-sky-200 dark:bg-sky-900/40 dark:text-sky-200 dark:border-sky-800",
  "bg-emerald-100 text-emerald-900 border-emerald-200 dark:bg-emerald-900/40 dark:text-emerald-200 dark:border-emerald-800",
  "bg-violet-100 text-violet-900 border-violet-200 dark:bg-violet-900/40 dark:text-violet-200 dark:border-violet-800",
  "bg-rose-100 text-rose-900 border-rose-200 dark:bg-rose-900/40 dark:text-rose-200 dark:border-rose-800",
];
const BACKLOG_BAR =
  "bg-slate-100 text-slate-700 border-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700";

function startOfWeek(base: Date): Date {
  const d = new Date(base.getFullYear(), base.getMonth(), base.getDate());
  d.setDate(d.getDate() - d.getDay()); // 일요일 시작
  return d;
}

function parseDate(iso: string): Date {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d);
}

function dayDiff(a: Date, b: Date): number {
  return Math.round((b.getTime() - a.getTime()) / DAY_MS);
}

export function TimelineView({
  board,
  onTaskClick,
}: {
  board: PlannerBoard;
  onTaskClick: (t: PlannerTask) => void;
}) {
  const [weekOffset, setWeekOffset] = useState(0);
  const today = useMemo(() => new Date(), []);
  const weekStart = useMemo(() => {
    const s = startOfWeek(today);
    s.setDate(s.getDate() + weekOffset * 7);
    return s;
  }, [today, weekOffset]);

  const days = useMemo(
    () => Array.from({ length: 7 }, (_, i) => new Date(weekStart.getTime() + i * DAY_MS)),
    [weekStart],
  );
  const weekEnd = days[6];

  const sprintColor = useMemo(() => {
    const m = new Map<number, string>();
    board.sprints.forEach((s, i) => m.set(s.id, BAR_PALETTE[i % BAR_PALETTE.length]));
    return m;
  }, [board.sprints]);

  // 이번 주와 겹치는 기간 태스크만 bar 로
  const bars = useMemo(() => {
    return board.tasks
      .filter((t) => t.startDate && t.dueDate)
      .map((t) => {
        const s = parseDate(t.startDate as string);
        const e = parseDate(t.dueDate as string);
        return { task: t, start: s, end: e };
      })
      .filter(({ start, end }) => start <= weekEnd && end >= weekStart)
      .map(({ task, start, end }) => {
        const colStart = Math.max(0, dayDiff(weekStart, start));
        const colEnd = Math.min(6, dayDiff(weekStart, end));
        return { task, colStart, span: colEnd - colStart + 1, days: dayDiff(start, end) + 1 };
      });
  }, [board.tasks, weekStart, weekEnd]);

  // 이번 주와 겹치는 스프린트 음영 밴드
  const bands = useMemo(() => {
    return board.sprints
      .map((s) => ({ s, start: parseDate(s.startDate), end: parseDate(s.endDate) }))
      .filter(({ start, end }) => start <= weekEnd && end >= weekStart)
      .map(({ s, start, end }) => ({
        sprint: s,
        colStart: Math.max(0, dayDiff(weekStart, start)),
        span: Math.min(6, dayDiff(weekStart, end)) - Math.max(0, dayDiff(weekStart, start)) + 1,
      }));
  }, [board.sprints, weekStart, weekEnd]);

  const unscheduled = board.tasks.filter((t) => !t.startDate || !t.dueDate);
  const isToday = (d: Date) =>
    d.getFullYear() === today.getFullYear() &&
    d.getMonth() === today.getMonth() &&
    d.getDate() === today.getDate();

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_240px]">
      <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-800">
        <div className="flex items-center justify-between gap-2">
          <h3 className="inline-flex items-center gap-2 text-sm font-bold text-slate-900 dark:text-slate-100">
            <CalendarClock className="h-4 w-4 text-indigo-600" />
            {weekStart.getFullYear()}년 {weekStart.getMonth() + 1}월
          </h3>
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => setWeekOffset((x) => x - 1)}
              className="rounded-lg border border-slate-200 p-1.5 text-slate-600 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-900"
              aria-label="이전 주"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <button
              type="button"
              onClick={() => setWeekOffset(0)}
              className="rounded-lg border border-slate-200 px-2.5 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-900"
            >
              오늘
            </button>
            <button
              type="button"
              onClick={() => setWeekOffset((x) => x + 1)}
              className="rounded-lg border border-slate-200 p-1.5 text-slate-600 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-900"
              aria-label="다음 주"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* 요일 헤더 */}
        <div className="mt-4 grid grid-cols-7 gap-1">
          {days.map((d, i) => (
            <div
              key={i}
              className={`rounded-lg py-1.5 text-center text-[11px] font-semibold ${
                isToday(d)
                  ? "bg-indigo-600 text-white"
                  : "text-slate-500 dark:text-slate-400"
              }`}
            >
              {WEEK_LABELS[d.getDay()]} {d.getDate()}
            </div>
          ))}
        </div>

        {/* 스프린트 음영 밴드 */}
        <div className="relative mt-1">
          {bands.map(({ sprint, colStart, span }) => (
            <div key={sprint.id} className="grid grid-cols-7 gap-1">
              <div
                className="mb-1 rounded-md bg-indigo-50/70 px-2 py-0.5 text-[10px] font-semibold text-indigo-500 dark:bg-indigo-900/15 dark:text-indigo-400"
                style={{ gridColumn: `${colStart + 1} / span ${span}` }}
              >
                {sprint.title}
              </div>
            </div>
          ))}

          {/* 태스크 bar */}
          <div className="mt-1 space-y-1.5">
            {bars.length === 0 ? (
              <p className="rounded-xl border border-dashed border-slate-200 p-8 text-center text-xs text-slate-400 dark:border-slate-700">
                이번 주에 걸친 일정이 없습니다. 카드에 시작일·마감일을 넣어보세요.
              </p>
            ) : (
              bars.map(({ task, colStart, span, days: totalDays }) => (
                <div key={task.id} className="grid grid-cols-7 gap-1">
                  <button
                    type="button"
                    onClick={() => onTaskClick(task)}
                    style={{ gridColumn: `${colStart + 1} / span ${span}` }}
                    className={`truncate rounded-lg border px-2.5 py-1.5 text-left text-[11px] font-semibold shadow-sm transition hover:shadow ${
                      task.sprintId != null
                        ? sprintColor.get(task.sprintId) ?? BACKLOG_BAR
                        : BACKLOG_BAR
                    } ${task.status === "done" ? "line-through opacity-60" : ""}`}
                  >
                    {task.title}
                    <span className="ml-1.5 font-normal opacity-70">{totalDays}일</span>
                  </button>
                </div>
              ))
            )}
          </div>
        </div>
      </section>

      {/* 일정 미정 패널 */}
      <section className="rounded-2xl border border-slate-200 bg-[#F8FAFC] p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900">
        <p className="text-xs font-bold text-slate-900 dark:text-slate-100">
          일정 미정 {unscheduled.length}건
        </p>
        <p className="mt-0.5 text-[11px] text-slate-500 dark:text-slate-500">
          클릭해 시작일·마감일을 부여하세요.
        </p>
        <div className="mt-3 space-y-2">
          {unscheduled.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => onTaskClick(t)}
              className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-left text-xs font-medium text-slate-800 shadow-sm transition hover:border-indigo-300 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
            >
              {t.title}
              {t.estimatedDays ? (
                <span className="ml-1 text-[10px] text-slate-400">약 {t.estimatedDays}일</span>
              ) : null}
            </button>
          ))}
          {unscheduled.length === 0 ? (
            <p className="text-center text-[11px] text-slate-400">모든 태스크에 일정이 있습니다.</p>
          ) : null}
        </div>
      </section>
    </div>
  );
}
```

- [ ] **Step 2: PlannerTab 분기 교체** — 플레이스홀더 `<p>…타임라인 뷰는 다음 단계…</p>`를 다음으로:

```tsx
        <TimelineView board={board} onTaskClick={(t) => setEditing(t)} />
```

상단 import 추가: `import { TimelineView } from "./TimelineView";`

- [ ] **Step 3: 빌드·라이브 확인**

Run: `pnpm lint` && `pnpm build` → 성공.
Preview: 타임라인 토글 → 요일 헤더·오늘 하이라이트·목업 bar 2개(스프린트 색상)·일정 미정 패널 렌더. bar 클릭 → 편집 패널. 주 이동 ◀▶ 동작.

- [ ] **Step 4: 커밋**

```powershell
git add www.yeotaeho.kr/src/components/features/roadmap/planner/TimelineView.tsx www.yeotaeho.kr/src/components/features/roadmap/planner/PlannerTab.tsx
git commit -m "feat(roadmap-fe): 주간 타임라인(간트) 뷰 — 7열 grid·기간 bar·일정 미정 패널"
```

---

### Task 9: 노트 탭 — 목록·에디터·미리보기·[[자동완성]]·백링크

**Files:**
- Create: `www.yeotaeho.kr/src/components/features/roadmap/notes/NotesTab.tsx`
- Create: `www.yeotaeho.kr/src/components/features/roadmap/notes/NoteEditor.tsx`
- Modify: `www.yeotaeho.kr/src/components/features/roadmap/RoadmapView.tsx` (notes 분기 추가 — Task 7 Step 1 참고)

**Interfaces:**
- Consumes: Task 6 `useNotesList`·`useNote`·`useCreateNote`·`useUpdateNote`·`useDeleteNote`, `NOTES_MOCK_LIST`·`NOTES_MOCK_DETAIL`.
- Produces: `NotesTab`, `NoteEditor({detail, allTitles, readOnly, saving, onSave, onOpenByTitle})`.
- 노트의 태스크/퀘스트 연결은 **표시 전용 칩**까지 구현(백엔드는 저장 지원 완료). 연결을 편집하는 picker UI와 태스크 카드의 노트 아이콘은 후속 과제로 이연 — Task 11 작업 기록의 "후속"에 명시할 것.

- [ ] **Step 1: NoteEditor 작성**

`www.yeotaeho.kr/src/components/features/roadmap/notes/NoteEditor.tsx`:

```tsx
"use client";

// 노트 에디터 — 편집(textarea)/미리보기(react-markdown) 토글, [[자동완성]], 백링크

import { Eye, Link2, PencilLine, Save } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import type { NoteDetail } from "@/lib/api/notes";

/** [[제목]] → 마크다운 링크(#note=제목)로 전처리 — 미리보기 클릭 이동용 */
function preprocessWikiLinks(content: string): string {
  return content.replace(/\[\[([^\[\]]+?)\]\]/g, (_, t: string) => {
    const title = t.trim();
    return `[${title}](#note=${encodeURIComponent(title)})`;
  });
}

export function NoteEditor({
  detail,
  allTitles,
  readOnly,
  saving,
  onSave,
  onOpenByTitle,
}: {
  detail: NoteDetail;
  allTitles: string[];
  readOnly: boolean;
  saving: boolean;
  onSave: (v: { title: string; content: string }) => void;
  onOpenByTitle: (title: string) => void;
}) {
  const [mode, setMode] = useState<"edit" | "preview">("preview");
  const [title, setTitle] = useState(detail.title);
  const [content, setContent] = useState(detail.content);
  const [autocomplete, setAutocomplete] = useState<{ query: string; at: number } | null>(null);
  const taRef = useRef<HTMLTextAreaElement>(null);

  // 다른 노트 선택 시 로컬 상태 리셋
  useEffect(() => {
    setTitle(detail.title);
    setContent(detail.content);
    setAutocomplete(null);
    setMode("preview");
  }, [detail.id, detail.title, detail.content]);

  const dirty = title !== detail.title || content !== detail.content;
  const existingTitles = useMemo(() => new Set(allTitles), [allTitles]);

  const suggestions = useMemo(() => {
    if (!autocomplete) return [];
    const q = autocomplete.query.toLowerCase();
    return allTitles
      .filter((t) => t !== detail.title && t.toLowerCase().includes(q))
      .slice(0, 6);
  }, [autocomplete, allTitles, detail.title]);

  const handleContentChange = (value: string, cursor: number) => {
    setContent(value);
    // 커서 앞에서 가장 가까운 "[[" 이후, "]]" 가 아직 닫히지 않았으면 자동완성
    const before = value.slice(0, cursor);
    const open = before.lastIndexOf("[[");
    if (open >= 0 && before.indexOf("]]", open) === -1) {
      setAutocomplete({ query: before.slice(open + 2), at: open });
    } else {
      setAutocomplete(null);
    }
  };

  const acceptSuggestion = (t: string) => {
    if (!autocomplete) return;
    const cursor = taRef.current?.selectionStart ?? content.length;
    const next = `${content.slice(0, autocomplete.at)}[[${t}]]${content.slice(cursor)}`;
    setContent(next);
    setAutocomplete(null);
    taRef.current?.focus();
  };

  const save = () => {
    if (!readOnly && dirty) onSave({ title: title.trim(), content });
  };

  return (
    <div
      className="flex h-full flex-col"
      onKeyDown={(e) => {
        if ((e.ctrlKey || e.metaKey) && e.key === "s") {
          e.preventDefault();
          save();
        }
      }}
    >
      <div className="flex items-center gap-2">
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          disabled={readOnly}
          className="w-full rounded-xl border border-transparent bg-transparent px-2 py-1.5 text-lg font-bold text-slate-900 focus:border-indigo-300 focus:outline-none dark:text-slate-100"
          placeholder="노트 제목"
        />
        <div className="flex shrink-0 rounded-xl border border-slate-200 p-0.5 dark:border-slate-700">
          <button
            type="button"
            onClick={() => setMode("edit")}
            disabled={readOnly}
            className={`rounded-lg p-1.5 ${mode === "edit" ? "bg-indigo-600 text-white" : "text-slate-500"}`}
            aria-label="편집"
          >
            <PencilLine className="h-3.5 w-3.5" />
          </button>
          <button
            type="button"
            onClick={() => setMode("preview")}
            className={`rounded-lg p-1.5 ${mode === "preview" ? "bg-indigo-600 text-white" : "text-slate-500"}`}
            aria-label="미리보기"
          >
            <Eye className="h-3.5 w-3.5" />
          </button>
        </div>
        {!readOnly ? (
          <button
            type="button"
            onClick={save}
            disabled={!dirty || saving}
            className="inline-flex shrink-0 items-center gap-1.5 rounded-xl bg-indigo-600 px-3 py-2 text-xs font-semibold text-white shadow-sm hover:bg-indigo-700 disabled:opacity-50"
          >
            <Save className="h-3.5 w-3.5" />
            {saving ? "저장 중…" : "저장"}
          </button>
        ) : null}
      </div>

      <div className="relative mt-3 flex-1">
        {mode === "edit" && !readOnly ? (
          <>
            <textarea
              ref={taRef}
              value={content}
              onChange={(e) => handleContentChange(e.target.value, e.target.selectionStart)}
              rows={18}
              className="h-full min-h-[360px] w-full resize-y rounded-2xl border border-slate-200 bg-white p-4 font-mono text-sm leading-relaxed text-slate-900 focus:border-indigo-300 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
              placeholder={"마크다운으로 기록하세요. [[다른 노트]] 로 연결할 수 있습니다."}
            />
            {suggestions.length > 0 ? (
              <div className="absolute left-4 top-16 z-10 w-64 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-lg dark:border-slate-700 dark:bg-slate-800">
                {suggestions.map((t) => (
                  <button
                    key={t}
                    type="button"
                    onClick={() => acceptSuggestion(t)}
                    className="block w-full px-3 py-2 text-left text-xs text-slate-800 hover:bg-indigo-50 dark:text-slate-200 dark:hover:bg-slate-700"
                  >
                    [[{t}]]
                  </button>
                ))}
              </div>
            ) : null}
          </>
        ) : (
          <div className="prose prose-sm prose-slate min-h-[360px] max-w-none rounded-2xl border border-slate-200 bg-white p-5 dark:prose-invert dark:border-slate-700 dark:bg-slate-800">
            <ReactMarkdown
              components={{
                a: ({ href, children }) => {
                  if (href?.startsWith("#note=")) {
                    const t = decodeURIComponent(href.slice(6));
                    const exists = existingTitles.has(t);
                    return (
                      <a
                        href={href}
                        onClick={(e) => {
                          e.preventDefault();
                          onOpenByTitle(t);
                        }}
                        className={
                          exists
                            ? "font-semibold text-indigo-600 no-underline hover:underline dark:text-indigo-400"
                            : "border-b border-dashed border-slate-400 font-semibold text-slate-500 no-underline"
                        }
                        title={exists ? t : `"${t}" — 아직 없는 노트`}
                      >
                        {children}
                      </a>
                    );
                  }
                  return (
                    <a href={href} target="_blank" rel="noreferrer">
                      {children}
                    </a>
                  );
                },
              }}
            >
              {preprocessWikiLinks(content) || "*빈 노트입니다.*"}
            </ReactMarkdown>
          </div>
        )}
      </div>

      {detail.questKey || detail.taskId != null ? (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {detail.questKey ? (
            <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-semibold text-slate-600 dark:bg-slate-700 dark:text-slate-300">
              🗺 퀘스트 연결 — {detail.questKey}
            </span>
          ) : null}
          {detail.taskId != null ? (
            <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] font-semibold text-slate-600 dark:bg-slate-700 dark:text-slate-300">
              📋 태스크 #{detail.taskId} 연결
            </span>
          ) : null}
        </div>
      ) : null}

      {detail.backlinks.length > 0 ? (
        <div className="mt-4 rounded-2xl border border-slate-200 bg-[#F8FAFC] p-4 dark:border-slate-700 dark:bg-slate-900">
          <p className="inline-flex items-center gap-1.5 text-xs font-bold text-slate-700 dark:text-slate-300">
            <Link2 className="h-3.5 w-3.5 text-indigo-500" />
            이 노트를 언급한 노트 {detail.backlinks.length}개
          </p>
          <div className="mt-2 flex flex-wrap gap-2">
            {detail.backlinks.map((b) => (
              <button
                key={b.id}
                type="button"
                onClick={() => onOpenByTitle(b.title)}
                className="rounded-full border border-indigo-100 bg-indigo-50 px-3 py-1 text-xs font-semibold text-indigo-800 hover:bg-indigo-100 dark:border-indigo-900/40 dark:bg-indigo-900/20 dark:text-indigo-300"
              >
                {b.title}
              </button>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}
```

- [ ] **Step 2: NotesTab 작성**

`www.yeotaeho.kr/src/components/features/roadmap/notes/NotesTab.tsx`:

```tsx
"use client";

// 노트 탭 — 좌측 목록(검색·생성) + 우측 마크다운 에디터, 비로그인 목업 폴백

import { NotebookPen, Plus, Search, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";
import { NOTES_MOCK_DETAIL, NOTES_MOCK_LIST } from "@/data/plannerMock";
import {
  useCreateNote,
  useDeleteNote,
  useNote,
  useNotesList,
  useUpdateNote,
} from "@/hooks/useNotes";
import type { NoteDetail } from "@/lib/api/notes";
import { useStore } from "@/store";
import { NoteEditor } from "./NoteEditor";

export function NotesTab() {
  const profile = useStore((s) => s.profile);
  const enabled = !!profile?.id;

  const { data: liveList } = useNotesList(enabled);
  const list = enabled && liveList ? liveList : NOTES_MOCK_LIST;

  const [selectedId, setSelectedId] = useState<number | null>(list[0]?.id ?? null);
  const [query, setQuery] = useState("");

  const { data: liveDetail } = useNote(selectedId, enabled);
  const detail: NoteDetail | null = enabled
    ? liveDetail ?? null
    : selectedId != null
      ? NOTES_MOCK_DETAIL[selectedId] ?? null
      : null;

  const createNote = useCreateNote();
  const updateNote = useUpdateNote();
  const deleteNote = useDeleteNote();

  const filtered = useMemo(
    () =>
      query.trim()
        ? list.filter(
            (n) =>
              n.title.toLowerCase().includes(query.toLowerCase()) ||
              n.preview.toLowerCase().includes(query.toLowerCase()),
          )
        : list,
    [list, query],
  );

  const allTitles = useMemo(() => list.map((n) => n.title), [list]);

  const handleCreate = (title?: string) => {
    if (!enabled) {
      window.alert("로그인하면 노트를 만들 수 있습니다.");
      return;
    }
    const name = (title ?? window.prompt("새 노트 제목"))?.trim();
    if (!name) return;
    createNote.mutate(
      { title: name },
      {
        onSuccess: (n) => setSelectedId(n.id),
        onError: () => window.alert("같은 제목의 노트가 이미 있습니다."),
      },
    );
  };

  const openByTitle = (title: string) => {
    const found = list.find((n) => n.title === title);
    if (found) setSelectedId(found.id);
    else if (enabled && window.confirm(`"${title}" 노트가 없습니다. 새로 만들까요?`)) {
      handleCreate(title);
    }
  };

  return (
    <div className="grid gap-4 lg:grid-cols-[280px_minmax(0,1fr)]">
      {/* 좌측 — 목록 */}
      <section className="flex flex-col rounded-2xl border border-slate-200 bg-[#F8FAFC] p-3 shadow-sm dark:border-slate-700 dark:bg-slate-900">
        <div className="flex items-center justify-between gap-2 px-1">
          <h2 className="inline-flex items-center gap-1.5 text-sm font-bold text-slate-900 dark:text-slate-100">
            <NotebookPen className="h-4 w-4 text-indigo-600" />
            노트
          </h2>
          <button
            type="button"
            onClick={() => handleCreate()}
            className="inline-flex items-center gap-1 rounded-lg bg-indigo-600 px-2 py-1.5 text-[11px] font-semibold text-white hover:bg-indigo-700"
          >
            <Plus className="h-3 w-3" />
            새 노트
          </button>
        </div>
        <div className="relative mt-2">
          <Search className="absolute left-2.5 top-2 h-3.5 w-3.5 text-slate-400" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="검색"
            className="w-full rounded-xl border border-slate-200 bg-white py-1.5 pl-8 pr-3 text-xs text-slate-900 focus:border-indigo-300 focus:outline-none dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
          />
        </div>
        {!enabled ? (
          <span className="mt-2 self-start rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-500 dark:bg-slate-800 dark:text-slate-400">
            예시 데이터
          </span>
        ) : null}
        <div className="mt-2 flex-1 space-y-1 overflow-y-auto">
          {filtered.map((n) => (
            <div key={n.id} className="group relative">
              <button
                type="button"
                onClick={() => setSelectedId(n.id)}
                className={`w-full rounded-xl border px-3 py-2 text-left transition ${
                  selectedId === n.id
                    ? "border-indigo-200 bg-white shadow-sm dark:border-indigo-800 dark:bg-slate-800"
                    : "border-transparent hover:bg-white/70 dark:hover:bg-slate-800/60"
                }`}
              >
                <p className="text-xs font-semibold text-slate-900 dark:text-slate-100">{n.title}</p>
                <p className="mt-0.5 line-clamp-1 text-[11px] text-slate-500 dark:text-slate-500">
                  {n.preview || "빈 노트"}
                </p>
              </button>
              {enabled ? (
                <button
                  type="button"
                  onClick={() => {
                    if (window.confirm(`"${n.title}" 노트를 삭제할까요?`)) {
                      deleteNote.mutate(n.id, {
                        onSuccess: () => {
                          if (selectedId === n.id) setSelectedId(null);
                        },
                      });
                    }
                  }}
                  className="absolute right-2 top-2 hidden rounded-md p-1 text-slate-300 hover:text-rose-500 group-hover:block"
                  aria-label="노트 삭제"
                >
                  <Trash2 className="h-3 w-3" />
                </button>
              ) : null}
            </div>
          ))}
          {filtered.length === 0 ? (
            <p className="p-4 text-center text-[11px] text-slate-400">노트가 없습니다.</p>
          ) : null}
        </div>
      </section>

      {/* 우측 — 에디터 */}
      <section className="min-h-[480px] rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-800">
        {detail ? (
          <NoteEditor
            key={detail.id}
            detail={detail}
            allTitles={allTitles}
            readOnly={!enabled}
            saving={updateNote.isPending}
            onSave={({ title, content }) =>
              updateNote.mutate(
                { id: detail.id, payload: { title, content } },
                { onError: () => window.alert("저장 실패 — 같은 제목의 노트가 있는지 확인하세요.") },
              )
            }
            onOpenByTitle={openByTitle}
          />
        ) : (
          <div className="flex h-full items-center justify-center">
            <p className="text-sm text-slate-400">좌측에서 노트를 선택하거나 새로 만드세요.</p>
          </div>
        )}
      </section>
    </div>
  );
}
```

- [ ] **Step 3: RoadmapView notes 분기 추가** — Task 7 Step 1의 최종 분기 형태로 (`NotesTab` import 포함).

- [ ] **Step 4: 빌드·라이브 확인**

Run: `pnpm lint` && `pnpm build` → 성공.
Preview: 노트 탭 → 목업 목록 2건, 상세 미리보기에서 `[[지표 용어집]]`이 링크로 렌더·클릭 시 해당 노트로 이동, 백링크 칩 렌더. 편집 모드에서 `[[` 입력 → 자동완성 드롭다운.

- [ ] **Step 5: 커밋**

```powershell
git add www.yeotaeho.kr/src/components/features/roadmap/notes/ www.yeotaeho.kr/src/components/features/roadmap/RoadmapView.tsx
git commit -m "feat(roadmap-fe): 노트 탭 — 마크다운 에디터·[[링크]] 자동완성·백링크"
```

---

### Task 10: AI 분해 버튼 + 여정 지도 태스크 진행률 배지

**Files:**
- Modify: `www.yeotaeho.kr/src/components/features/roadmap/planner/PlannerTab.tsx` (백로그 상단 AI 분해 UI)
- Modify: `www.yeotaeho.kr/src/components/features/roadmap/planner/BoardView.tsx` (백로그 컬럼에 `decomposeSlot` 렌더 prop)
- Modify: `www.yeotaeho.kr/src/components/features/roadmap/JourneyMapTab.tsx` (퀘스트 카드에 "태스크 n/m" 배지)

**Interfaces:**
- Consumes: Task 6 `useDecomposeQuest`, `usePlannerBoard`; `flattenQuestTitles`.
- Produces: 보드 백로그 상단 — 퀘스트 select + "AI로 분해" 버튼 (로딩 스피너, 이미 분해된 퀘스트는 "이미 n개" 경고 후 확인 진행). 여정 카드 — `연결 태스크 n/m` 칩(n=done).

- [ ] **Step 1: BoardView에 decomposeSlot prop 추가** — `BoardView` props에 `decomposeSlot?: React.ReactNode` 추가하고, 백로그 `Column` 바로 위(백로그 섹션 내부 상단)에 렌더. `Column` 컴포넌트에 `headerExtra?: React.ReactNode` prop을 추가해 백로그 컬럼에만 전달:

`Column` 헤더 div 아래(진행률 바 위)에 삽입:

```tsx
      {headerExtra}
```

`BoardView` 백로그 Column 호출에 전달:

```tsx
          headerExtra={decomposeSlot}
```

- [ ] **Step 2: PlannerTab에 분해 UI 추가** — `useDecomposeQuest` import, 컴포넌트 내부:

```tsx
  const decompose = useDecomposeQuest();
  const [decomposeKey, setDecomposeKey] = useState("");

  const questOptions = useMemo(
    () => Array.from(questTitles.entries()).filter(([k]) => k !== "root"),
    [questTitles],
  );

  const handleDecompose = () => {
    if (!decomposeKey) return;
    const existing = board.tasks.filter((t) => t.questKey === decomposeKey).length;
    if (
      existing > 0 &&
      !window.confirm(`이 퀘스트는 이미 ${existing}개 태스크로 분해되어 있습니다. 추가로 분해할까요?`)
    ) {
      return;
    }
    decompose.mutate(decomposeKey);
  };
```

`BoardView`에 전달할 slot (로그인 시에만):

```tsx
        decomposeSlot={
          enabled ? (
            <div className="mt-2 space-y-1.5 rounded-xl border border-indigo-100 bg-indigo-50/60 p-2 dark:border-indigo-900/40 dark:bg-indigo-900/15">
              <select
                value={decomposeKey}
                onChange={(e) => setDecomposeKey(e.target.value)}
                className="w-full rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-[11px] text-slate-800 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
              >
                <option value="">퀘스트 선택…</option>
                {questOptions.map(([key, title]) => (
                  <option key={key} value={key}>
                    {title}
                  </option>
                ))}
              </select>
              <button
                type="button"
                onClick={handleDecompose}
                disabled={!decomposeKey || decompose.isPending}
                className="inline-flex w-full items-center justify-center gap-1.5 rounded-lg bg-indigo-600 px-2 py-1.5 text-[11px] font-semibold text-white hover:bg-indigo-700 disabled:opacity-60"
              >
                <Sparkles className="h-3 w-3" />
                {decompose.isPending ? "분해 중…" : "AI로 분해"}
              </button>
            </div>
          ) : null
        }
```

(`Sparkles`는 lucide-react에서 import 추가.)

- [ ] **Step 3: JourneyMapTab 진행률 배지** — import 추가:

```typescript
import { usePlannerBoard } from "@/hooks/usePlanner";
```

`JourneyMapTab` 본문에서 태스크 카운트 맵 계산:

```tsx
  const { data: plannerData } = usePlannerBoard(loggedIn);
  const taskCounts = useMemo(() => {
    const m = new Map<string, { done: number; total: number }>();
    for (const t of plannerData?.tasks ?? []) {
      if (!t.questKey) continue;
      const cur = m.get(t.questKey) ?? { done: 0, total: 0 };
      cur.total += 1;
      if (t.status === "done") cur.done += 1;
      m.set(t.questKey, cur);
    }
    return m;
  }, [plannerData]);
```

(`useMemo`는 react에서 import 추가.) `QuestTreeCard`에 `taskCounts` prop 전달하고, 카드의 난이도 칩 옆에:

```tsx
            {counts && counts.total > 0 ? (
              <span className="inline-flex items-center gap-0.5 rounded-full bg-sky-100 px-2 py-0.5 text-[10px] font-semibold text-sky-800 dark:bg-sky-900/35 dark:text-sky-300">
                태스크 {counts.done}/{counts.total}
              </span>
            ) : null}
```

`QuestTreeCard` 시그니처 변경 및 재귀 전달:

```tsx
function QuestTreeCard({
  node,
  depth,
  taskCounts,
}: {
  node: QuestTreeNode;
  depth: number;
  taskCounts?: Map<string, { done: number; total: number }>;
}) {
  const counts = taskCounts?.get(node.id);
  // …기존 본문…
  // children 재귀: <QuestTreeCard key={ch.id} node={ch} depth={depth + 1} taskCounts={taskCounts} />
```

호출부: `<QuestTreeCard node={tree} depth={0} taskCounts={taskCounts} />`

- [ ] **Step 4: 빌드·라이브 확인**

Run: `pnpm lint` && `pnpm build` → 성공.
Preview: 백로그 상단에 퀘스트 select + "AI로 분해" 버튼 렌더(로그인 시). 여정 지도에서 목업/라이브 태스크가 연결된 퀘스트에 "태스크 n/m" 배지.

- [ ] **Step 5: 커밋**

```powershell
git add www.yeotaeho.kr/src/components/features/roadmap/planner/PlannerTab.tsx www.yeotaeho.kr/src/components/features/roadmap/planner/BoardView.tsx www.yeotaeho.kr/src/components/features/roadmap/JourneyMapTab.tsx
git commit -m "feat(roadmap-fe): AI 퀘스트 분해 버튼 + 여정 지도 태스크 진행률 배지"
```

---

### Task 11: 통합 검증 · 작업 기록 · 이중 리뷰

**Files:**
- Modify: `backend/domain/hrowth_journey/docs/audit_trail.md` (작업 기록 — **작성 전 사용자에게 경로 제시·허락 필수**, 파일이 없으면 생성 허락도 함께)

- [ ] **Step 1: 백엔드 전체 테스트 재실행**

Run (backend/): `python scripts/planner_decompose_parse_test.py; python scripts/planner_service_test.py; python scripts/roadmap_note_links_test.py; python scripts/roadmap_planner_parse_test.py; python scripts/roadmap_journey_assembler_test.py`
Expected: 전부 FAIL 0

- [ ] **Step 2: 프론트 최종 빌드**

Run (www.yeotaeho.kr/): `pnpm lint; pnpm build`
Expected: 에러 0

- [ ] **Step 3: 라이브 검증 (Claude Preview)** — 로그인 세션으로:
  1. 플래너: 스프린트 생성 → 태스크 생성 → 백로그↔스프린트 드래그 → 새로고침 후 유지(영속) 확인.
  2. 타임라인: 태스크에 날짜 부여 → bar 렌더 → 주 이동.
  3. AI 분해: 퀘스트 선택 → 분해 → 백로그에 AI 배지 태스크 3~6개 (OPENAI_API_KEY 없으면 폴백 3개).
  4. 노트: 생성 → `[[다른 노트]]` 링크 저장 → 상대 노트에서 백링크 확인 → 제목 중복 409 경고.
  5. 스크린샷 증빙 저장(보드·타임라인·노트 각 1장).

- [ ] **Step 4: 작업 기록** — 사용자에게 `backend/domain/hrowth_journey/docs/audit_trail.md` 경로 허락 요청 후 기록 형식(무엇/왜/어디/검증/후속)으로 최신 항목 추가, 커밋:

```powershell
git add backend/domain/hrowth_journey/docs/audit_trail.md
git commit -m "docs(roadmap): 플래너·노트 구현 감사 기록"
```

- [ ] **Step 5: 이중 리뷰** — CLAUDE.md 코드 리뷰 규칙:
  1. `Agent` 도구 `subagent_type: "code-reviewer"` — 변경 범위: `feat/roadmap-planner-notes` 브랜치 전체 커밋. Critical/Important 조치 후,
  2. `/codex:review --base <분기 시점 ref> --scope branch` (background) — 지적사항은 실제 결함인지 판단 후 반영, Critical/Important 는 재리뷰.
