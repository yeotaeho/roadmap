# 선택적 사용자 데이터 개인화 — Phase 2(임베딩 통합) 구현 플랜

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Phase 1에서 수집한 성향·스펙을 사용자 임베딩 텍스트에 직렬화하고, 데이터 변경 시 재임베딩되게 하며, Chance 매칭의 키워드 가산에도 반영해 Sync/Chance 개인화 품질을 끌어올린다.

**Architecture:** 순수 헬퍼 모듈(`user_embed_text.py`)이 성향 enum→한국어 라벨·스펙 용어를 직렬화한다(테스트 용이·DRY). `embed_service._user_text`가 이를 위임하고, `embed_repository`의 미임베딩 사용자 쿼리가 user_preferences·user_personas를 LEFT JOIN하며 `updated_at > computed_at` 타임스탬프로 재임베딩 대상을 재선택한다(해시 동일 시 임베딩 생략). Chance는 같은 헬퍼로 user_terms를 확장한다. **스키마 변경 없음.**

**Tech Stack:** SQLAlchemy 2.0(async) · asyncpg(JSONB→Python 객체) · OpenAI text-embedding-3-large(halfvec 3072) · 순수함수 + 인프로세스 DB 테스트.

## Global Constraints

- 새 소스 파일 첫 줄 한 줄 한국어 주석. 한국어 종결 `.` `?` `!` 만. 소스는 UTF-8(한글 OK), 콘솔 출력용 비ASCII 특수문자(em-dash 등) 지양.
- **데모그래픽(user_profiles: 나이·성별·지역·현재상태·학력)은 임베딩 직렬화·매칭에 사용 금지**(편향·노이즈 방지). user_profiles 는 이 Phase 에서 JOIN/참조하지 않는다.
- 임베딩 대상 의미 데이터: 직무·관심키워드(기존) + 성향(work_style·company_size_pref·work_type_pref·work_values) + 스펙(skills.name·certifications.name·languages.language·projects.title·projects.tech_stack).
- 기존 `_user_text(target_job, interest_keywords)` 2-인자 호출 결과는 불변(하위호환). 신규 필드가 전부 빈값이면 출력 동일.
- JSONB 컬럼은 asyncpg 가 이미 Python list/dict 로 파싱(기존 persona_repository 패턴). 헬퍼는 list/dict 입력 가정.
- 멱등: 동일 입력 텍스트(해시 동일)는 재임베딩하지 않는다. OpenAI 키 없으면 임베딩 단계 skip(기존 관례).
- 테스트는 기존 컨벤션(`scripts/*_test.py`, `check()` 기반). 순수 테스트는 무DB·무네트워크. DB 테스트는 Neon 인프로세스(시드 사용자, 멱등). OpenAI 호출 테스트는 키 없으면 graceful skip.
- 커밋은 태스크(수직)마다. pycache 등 무관 변경 묶지 않기.

---

### Task 1: 순수 헬퍼 `user_embed_text.py` — 성향·스펙 직렬화 + 테스트

**Files:**
- Create: `domain/market_insight/hub/services/user_embed_text.py`
- Test: `scripts/user_embed_text_test.py`

**Interfaces:**
- Produces:
  - `disposition_spec_terms(work_style=None, company_size_pref=None, work_type_pref=None, work_values=None, skills=None, certifications=None, languages=None, projects=None) -> list[str]` — 성향·스펙을 한국어 용어 리스트로. 순수.
  - `build_user_embed_text(target_job=None, interest_keywords=None, work_style=None, company_size_pref=None, work_type_pref=None, work_values=None, skills=None, certifications=None, languages=None, projects=None) -> str` — 한 줄 임베딩 텍스트. 빈 입력은 `"_"`.
  - 라벨 dict `_WORK_STYLE_LABEL`·`_COMPANY_SIZE_LABEL`·`_WORK_TYPE_LABEL`·`_WORK_VALUE_LABEL`.

- [ ] **Step 1: 테스트 작성**

`scripts/user_embed_text_test.py`:

```python
# 사용자 임베딩 텍스트 헬퍼(성향·스펙 직렬화) 무네트워크 결정론 테스트

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from domain.market_insight.hub.services.user_embed_text import (  # noqa: E402
    build_user_embed_text,
    disposition_spec_terms,
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


def run() -> int:
    # 하위호환: 직무+관심만 → 기존 _user_text 와 동일 출력
    check("직무+관심 결합", build_user_embed_text("데이터 분석가", ["AI", "핀테크"]) == "데이터 분석가 AI 핀테크")
    check("관심만", build_user_embed_text(None, ["AI"]) == "AI")
    check("빈 입력 → 플레이스홀더", build_user_embed_text(None, []) == "_")
    check("비-리스트 관심 무시", build_user_embed_text("기획자", None) == "기획자")

    # 성향 라벨 매핑
    terms = disposition_spec_terms(
        work_style="challenge", company_size_pref="startup",
        work_type_pref="hybrid", work_values=["growth", "autonomy"],
    )
    check("work_style 라벨", "도전 지향" in terms, str(terms))
    check("company_size 라벨", "스타트업" in terms)
    check("work_type 라벨", "하이브리드 근무" in terms)
    check("work_values 라벨 2개", "성장" in terms and "자율성" in terms)
    check("미지의 enum 무시", disposition_spec_terms(work_style="bogus") == [])

    # 스펙 추출
    spec = disposition_spec_terms(
        skills=[{"name": "Python", "level": "중급"}, {"name": "SQL"}],
        certifications=[{"name": "정보처리기사", "issuer": "큐넷"}],
        languages=[{"language": "영어", "test": "TOEIC"}],
        projects=[{"title": "추천엔진", "tech_stack": ["FastAPI", "pgvector"]}],
    )
    check("skill 이름", "Python" in spec and "SQL" in spec)
    check("자격증 이름", "정보처리기사" in spec)
    check("어학 언어", "영어" in spec)
    check("프로젝트 제목", "추천엔진" in spec)
    check("tech_stack 전개", "FastAPI" in spec and "pgvector" in spec)

    # 통합 직렬화
    full = build_user_embed_text(
        "백엔드", ["AI"], work_style="challenge", work_values=["growth"],
        skills=[{"name": "Python"}],
    )
    check("통합 텍스트 포함", all(w in full for w in ("백엔드", "AI", "도전 지향", "성장", "Python")), full)
    check("None/빈 dict 견고", disposition_spec_terms(skills=[None, {}, {"name": ""}]) == [])

    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(run())
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `python scripts/user_embed_text_test.py`
Expected: FAIL — `ModuleNotFoundError: ... user_embed_text`.

- [ ] **Step 3: 헬퍼 구현**

`domain/market_insight/hub/services/user_embed_text.py`:

```python
# 사용자 임베딩/매칭용 텍스트 직렬화 — 성향·스펙 enum→한국어 라벨 (순수, 무DB·무네트워크)

from __future__ import annotations

_WORK_STYLE_LABEL = {"stability": "안정 지향", "challenge": "도전 지향", "balanced": "균형 지향"}
_COMPANY_SIZE_LABEL = {"startup": "스타트업", "sme": "중소기업", "large": "대기업", "public": "공공기관"}
_WORK_TYPE_LABEL = {"office": "사무실 근무", "remote": "원격 근무", "hybrid": "하이브리드 근무"}
_WORK_VALUE_LABEL = {
    "growth": "성장",
    "work_life_balance": "워라밸",
    "autonomy": "자율성",
    "impact": "사회적 임팩트",
    "compensation": "보상",
}


def _names(items, key: str) -> list[str]:
    """JSONB 리스트[{key:..}]에서 key 값 문자열만 추출(None·비dict·빈값 무시)."""
    out: list[str] = []
    if isinstance(items, list):
        for it in items:
            if isinstance(it, dict):
                v = it.get(key)
                if v:
                    out.append(str(v))
    return out


def _tech_stack(projects) -> list[str]:
    """projects[].tech_stack 의 모든 기술 문자열을 평탄화한다."""
    out: list[str] = []
    if isinstance(projects, list):
        for p in projects:
            if isinstance(p, dict) and isinstance(p.get("tech_stack"), list):
                out.extend(str(t) for t in p["tech_stack"] if t)
    return out


def disposition_spec_terms(
    work_style=None,
    company_size_pref=None,
    work_type_pref=None,
    work_values=None,
    skills=None,
    certifications=None,
    languages=None,
    projects=None,
) -> list[str]:
    """성향·스펙을 임베딩/매칭용 한국어 용어 리스트로 변환한다. 순수·결정론."""
    terms: list[str] = []
    if work_style in _WORK_STYLE_LABEL:
        terms.append(_WORK_STYLE_LABEL[work_style])
    if company_size_pref in _COMPANY_SIZE_LABEL:
        terms.append(_COMPANY_SIZE_LABEL[company_size_pref])
    if work_type_pref in _WORK_TYPE_LABEL:
        terms.append(_WORK_TYPE_LABEL[work_type_pref])
    if isinstance(work_values, list):
        terms.extend(_WORK_VALUE_LABEL[v] for v in work_values if v in _WORK_VALUE_LABEL)
    terms += _names(skills, "name")
    terms += _names(certifications, "name")
    terms += _names(languages, "language")
    terms += _names(projects, "title")
    terms += _tech_stack(projects)
    return terms


def build_user_embed_text(
    target_job=None,
    interest_keywords=None,
    work_style=None,
    company_size_pref=None,
    work_type_pref=None,
    work_values=None,
    skills=None,
    certifications=None,
    languages=None,
    projects=None,
) -> str:
    """직무+관심키워드+성향+스펙을 한 줄 임베딩 텍스트로 직렬화한다. 빈 입력은 '_'."""
    kws = interest_keywords if isinstance(interest_keywords, list) else []
    parts = ([target_job] if target_job else []) + [str(k) for k in kws]
    parts += disposition_spec_terms(
        work_style, company_size_pref, work_type_pref, work_values,
        skills, certifications, languages, projects,
    )
    return " ".join(p for p in parts if p).strip() or "_"
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

Run: `python scripts/user_embed_text_test.py`
Expected: PASS — 전 체크 PASS, FAIL=0.

- [ ] **Step 5: 커밋**

```bash
git add domain/market_insight/hub/services/user_embed_text.py scripts/user_embed_text_test.py
git commit -m "feat(embed): 사용자 성향·스펙 임베딩 텍스트 직렬화 순수 헬퍼"
```

---

### Task 2: embed 쿼리 JOIN + 재임베딩 트리거 + `_user_text` 위임

**Files:**
- Modify: `domain/market_insight/hub/repositories/embed_repository.py` (`_FETCH_UNEMBEDDED_USERS`)
- Modify: `domain/market_insight/hub/services/embed_service.py` (`_user_text` 위임, `embed_users` 신규 필드·해시 스킵)
- Test: `scripts/user_reembed_test.py`

**Interfaces:**
- Consumes: Task 1 `build_user_embed_text`. Phase 1 테이블 user_preferences·user_personas(updated_at), user_embeddings(source_version·computed_at).
- Produces: `fetch_unembedded_users` 가 신규 컬럼(work_style·…·projects·source_version) 포함 + `updated_at > computed_at` 인 사용자 재선택. `embed_users` 가 풍부한 텍스트로 임베딩하되 해시 동일 사용자는 생략.

- [ ] **Step 1: 통합 테스트 작성(재임베딩 선택 검증)**

`scripts/user_reembed_test.py`:

```python
# 사용자 재임베딩 선택·직렬화 통합 테스트 — 데이터 변경 시 미임베딩 큐에 재진입하는지

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

from sqlalchemy import text  # noqa: E402

from core.config.settings import get_settings  # noqa: E402
from core.database import AsyncSessionLocal  # noqa: E402
from domain.market_insight.hub.repositories.embed_repository import EmbedRepository  # noqa: E402
from domain.market_insight.hub.services.embed_service import UserEmbedService  # noqa: E402

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


async def _seed_user(s) -> str:
    r = (await s.execute(text("SELECT id FROM users ORDER BY created_at LIMIT 1"))).first()
    if r is None:
        raise SystemExit("users 테이블이 비어 있습니다.")
    uid = str(r.id)
    # 시드 사용자에 sync_profile 보장(없으면 생성).
    await s.execute(
        text(
            """
            INSERT INTO user_sync_profiles (user_id, target_job, interest_keywords, updated_at)
            VALUES (CAST(:uid AS UUID), :job, CAST(:kw AS JSONB), now())
            ON CONFLICT (user_id) DO UPDATE SET target_job = EXCLUDED.target_job, updated_at = now()
            """
        ),
        {"uid": uid, "job": "백엔드 엔지니어", "kw": '["AI"]'},
    )
    await s.commit()
    return uid


async def run() -> int:
    settings = get_settings()
    model = settings.llm_embed_model

    async with AsyncSessionLocal() as s:
        uid = await _seed_user(s)
        repo = EmbedRepository(s)

        # Part A — fetch 가 신규 컬럼을 반환하는가(DB-only).
        rows = await repo.fetch_unembedded_users(model, 300)
        seed_rows = [r for r in rows if str(r.user_id) == uid]
        # 시드 사용자가 (임베딩 없거나 방금 sync 갱신으로) 큐에 있어야 한다.
        check("fetch 컬럼: work_style", hasattr(rows[0] if rows else seed_rows[0], "work_style"))
        check("fetch 컬럼: skills", hasattr(rows[0] if rows else seed_rows[0], "skills"))
        check("fetch 컬럼: source_version", hasattr(rows[0] if rows else seed_rows[0], "source_version"))

        # Part B — 성향 변경 후 재선택되는가(DB-only).
        await s.execute(
            text(
                """
                INSERT INTO user_preferences (user_id, work_style, source, updated_at)
                VALUES (CAST(:uid AS UUID), 'challenge', 'user_form', now())
                ON CONFLICT (user_id) DO UPDATE SET work_style = 'challenge', updated_at = now()
                """
            ),
            {"uid": uid},
        )
        await s.commit()
        rows2 = await repo.fetch_unembedded_users(model, 300)
        check("성향 변경 후 재선택", any(str(r.user_id) == uid for r in rows2), f"uid={uid}")
        sel = [r for r in rows2 if str(r.user_id) == uid][0]
        check("재선택 행 work_style=challenge", sel.work_style == "challenge", str(sel.work_style))

    # Part C — OpenAI 키 있으면 실제 재임베딩 사이클(없으면 skip).
    if settings.openai_api_key:
        async with AsyncSessionLocal() as s:
            svc = UserEmbedService(s)
            res = await svc.embed_users(limit=300)
            check("embed_users scanned≥1", res["scanned"] >= 1, str(res))
            repo = EmbedRepository(s)
            rows3 = await repo.fetch_unembedded_users(model, 300)
            check("임베딩 후 시드 미선택(멱등)", all(str(r.user_id) != uid for r in rows3), f"uid={uid}")
    else:
        print("[SKIP] OPENAI_API_KEY 없음 — Part C(실제 임베딩) 생략")

    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `python scripts/user_reembed_test.py`
Expected: FAIL — `fetch 컬럼: work_style` 등 실패(현재 쿼리는 work_style 미반환) 또는 `성향 변경 후 재선택` 실패(현재 IS NULL 만 봄).

- [ ] **Step 3: `_FETCH_UNEMBEDDED_USERS` 쿼리 교체**

`embed_repository.py` 의 `_FETCH_UNEMBEDDED_USERS` 를 다음으로 교체:

```python
_FETCH_UNEMBEDDED_USERS = text(
    """
    SELECT p.user_id, p.target_job, p.interest_keywords,
           pref.work_style, pref.company_size_pref, pref.work_type_pref, pref.work_values,
           per.skills, per.certifications, per.languages, per.projects,
           e.source_version
    FROM user_sync_profiles p
    LEFT JOIN user_preferences pref ON pref.user_id = p.user_id
    LEFT JOIN user_personas per ON per.user_id = p.user_id
    LEFT JOIN user_embeddings e ON e.user_id = p.user_id AND e.embedding_model = :model
    WHERE e.user_id IS NULL
       OR GREATEST(
            p.updated_at,
            COALESCE(pref.updated_at, p.updated_at),
            COALESCE(per.updated_at, p.updated_at)
          ) > e.computed_at
    LIMIT :lim
    """
)
```

(데모그래픽 user_profiles 는 JOIN 하지 않는다 — Global Constraints.)

- [ ] **Step 4: `embed_service` 의 `_user_text` 위임 + `embed_users` 갱신**

`embed_service.py` 상단 import 추가:

```python
from domain.market_insight.hub.services.user_embed_text import build_user_embed_text
```

`UserEmbedService._user_text` 를 다음으로 교체(2-인자 하위호환 유지, 신규 필드 위임):

```python
    @staticmethod
    def _user_text(
        target_job, interest_keywords, work_style=None, company_size_pref=None,
        work_type_pref=None, work_values=None, skills=None, certifications=None,
        languages=None, projects=None,
    ) -> str:
        return build_user_embed_text(
            target_job, interest_keywords, work_style, company_size_pref, work_type_pref,
            work_values, skills, certifications, languages, projects,
        )
```

`embed_users` 를 다음으로 교체(풍부한 텍스트 + 해시 동일 시 생략):

```python
    async def embed_users(self, limit: int = DEFAULT_LIMIT) -> dict:
        rows = await self.repo.fetch_unembedded_users(self._model, limit)
        # 텍스트·해시 산출 후, 저장된 해시와 동일하면(타임스탬프상 후보지만 내용 불변) 임베딩 생략.
        pending = []
        for r in rows:
            t = self._user_text(
                r.target_job, r.interest_keywords,
                r.work_style, r.company_size_pref, r.work_type_pref, r.work_values,
                r.skills, r.certifications, r.languages, r.projects,
            )
            version = hashlib.sha256(t.encode("utf-8")).hexdigest()[:16]
            if version != r.source_version:
                pending.append((r.user_id, t, version))
        embedded = 0
        for i in range(0, len(pending), _BATCH):
            chunk = pending[i : i + _BATCH]
            vectors = await self._llm.embed([t for _, t, _ in chunk])
            for (uid, _t, version), vec in zip(chunk, vectors):
                await self.repo.upsert_user_embedding(uid, vec, version, self._model)
                embedded += 1
            await self.session.commit()
        return {"scanned": len(rows), "embedded": embedded}
```

- [ ] **Step 5: 테스트 실행 → 통과 확인**

Run: `python scripts/user_reembed_test.py`
Expected: PASS — Part A·B PASS. OPENAI_API_KEY 있으면 Part C 도 PASS(scanned≥1·멱등 미선택), 없으면 `[SKIP]` 출력 후 FAIL=0.

- [ ] **Step 6: 기존 임베딩 헬퍼 테스트 회귀 확인**

Run: `python scripts/embed_helpers_test.py`
Expected: PASS — 기존 `_user_text` 2-인자 테스트가 위임 후에도 동일 출력으로 통과(하위호환).

- [ ] **Step 7: 커밋**

```bash
git add domain/market_insight/hub/repositories/embed_repository.py domain/market_insight/hub/services/embed_service.py scripts/user_reembed_test.py
git commit -m "feat(embed): 성향·스펙 임베딩 직렬화 + updated_at 기반 재임베딩 트리거"
```

---

### Task 3: Chance 매칭 user_terms 에 성향·스펙 가산

**Files:**
- Modify: `domain/market_insight/hub/repositories/chance_repository.py` (`_FETCH_USERS`)
- Modify: `domain/market_insight/hub/services/chance_match_service.py` (`user_terms` 확장)
- Test: `scripts/chance_user_terms_test.py`

**Interfaces:**
- Consumes: Task 1 `disposition_spec_terms`. Phase 1 user_preferences·user_personas.
- Produces: `ChanceRepository.fetch_users()` 가 성향·스펙 컬럼 포함. `match_all` 의 `user_terms` 에 성향·스펙 한국어 용어 가산(키워드 보조 매칭 강화).

- [ ] **Step 1: 테스트 작성**

`scripts/chance_user_terms_test.py`:

```python
# Chance user_terms 성향·스펙 가산 통합 테스트 — fetch_users 컬럼 + 매칭 스모크

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

from sqlalchemy import text  # noqa: E402

from core.database import AsyncSessionLocal  # noqa: E402
from domain.market_insight.hub.repositories.chance_repository import ChanceRepository  # noqa: E402
from domain.market_insight.hub.services.user_embed_text import disposition_spec_terms  # noqa: E402

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


async def run() -> int:
    async with AsyncSessionLocal() as s:
        r = (await s.execute(text("SELECT id FROM users ORDER BY created_at LIMIT 1"))).first()
        if r is None:
            raise SystemExit("users 테이블이 비어 있습니다.")
        uid = str(r.id)
        # 시드 사용자에 sync_profile + 성향 보장.
        await s.execute(
            text(
                """
                INSERT INTO user_sync_profiles (user_id, target_job, interest_keywords, updated_at)
                VALUES (CAST(:uid AS UUID), '백엔드', CAST('["AI"]' AS JSONB), now())
                ON CONFLICT (user_id) DO UPDATE SET updated_at = now()
                """
            ),
            {"uid": uid},
        )
        await s.execute(
            text(
                """
                INSERT INTO user_preferences (user_id, work_style, work_values, source, updated_at)
                VALUES (CAST(:uid AS UUID), 'challenge', CAST('["growth"]' AS JSONB), 'user_form', now())
                ON CONFLICT (user_id) DO UPDATE SET work_style = 'challenge', work_values = CAST('["growth"]' AS JSONB), updated_at = now()
                """
            ),
            {"uid": uid},
        )
        await s.commit()

        repo = ChanceRepository(s)
        users = await repo.fetch_users()
        check("fetch_users 비어있지 않음", len(users) >= 1)
        check("fetch_users 컬럼: work_style", hasattr(users[0], "work_style"))
        check("fetch_users 컬럼: skills", hasattr(users[0], "skills"))
        seed = [u for u in users if str(u.user_id) == uid]
        check("시드 사용자 포함", len(seed) == 1)
        u = seed[0]
        terms = disposition_spec_terms(
            u.work_style, u.company_size_pref, u.work_type_pref, u.work_values,
            u.skills, u.certifications, u.languages, u.projects,
        )
        check("성향 용어 가산(도전 지향)", "도전 지향" in terms, str(terms))
        check("가치 용어 가산(성장)", "성장" in terms)

    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `python scripts/chance_user_terms_test.py`
Expected: FAIL — `fetch_users 컬럼: work_style` 실패(현재 user_sync_profiles 만 SELECT).

- [ ] **Step 3: `_FETCH_USERS` 쿼리 확장**

`chance_repository.py` 의 `_FETCH_USERS` 를 다음으로 교체:

```python
_FETCH_USERS = text(
    """
    SELECT p.user_id, p.target_job, p.interest_keywords,
           pref.work_style, pref.company_size_pref, pref.work_type_pref, pref.work_values,
           per.skills, per.certifications, per.languages, per.projects
    FROM user_sync_profiles p
    LEFT JOIN user_preferences pref ON pref.user_id = p.user_id
    LEFT JOIN user_personas per ON per.user_id = p.user_id
    """
)
```

- [ ] **Step 4: `chance_match_service` 의 user_terms 확장**

`chance_match_service.py` 상단 import 추가:

```python
from domain.market_insight.hub.services.user_embed_text import disposition_spec_terms
```

`match_all` 의 user_terms 구성(현재 `user_terms = list(keywords) + ([u.target_job] if u.target_job else [])`)을 다음으로 교체:

```python
            user_terms = (
                list(keywords)
                + ([u.target_job] if u.target_job else [])
                + disposition_spec_terms(
                    u.work_style, u.company_size_pref, u.work_type_pref, u.work_values,
                    u.skills, u.certifications, u.languages, u.projects,
                )
            )
```

(섹터 가산용 `keywords`/`_sector_hit` 신호는 기존 interest_keywords 만 유지 — 성향·스펙은 직접 term 매칭에만 가산.)

- [ ] **Step 5: 테스트 실행 → 통과 확인**

Run: `python scripts/chance_user_terms_test.py`
Expected: PASS — fetch_users 신규 컬럼 + 성향·스펙 용어 가산 확인, FAIL=0.

- [ ] **Step 6: Chance 매칭 회귀 스모크(기존 테스트)**

Run: `python scripts/chance_extract_match_test.py`
Expected: 기존 순수 매칭 테스트가 그대로 PASS(user_terms 확장은 입력만 늘릴 뿐 `semantic_match_score`/`score_match` 시그니처 불변).

- [ ] **Step 7: 커밋**

```bash
git add domain/market_insight/hub/repositories/chance_repository.py domain/market_insight/hub/services/chance_match_service.py scripts/chance_user_terms_test.py
git commit -m "feat(chance): 매칭 user_terms 에 성향·스펙 용어 가산"
```

---

## Phase 2 완료 기준

- `user_embed_text_test.py`·`user_reembed_test.py`·`chance_user_terms_test.py` 전부 FAIL=0(OpenAI 키 없으면 Part C SKIP 허용).
- 회귀: `embed_helpers_test.py`·`chance_extract_match_test.py` PASS.
- 사용자가 성향·스펙을 채우면 (a) 임베딩 텍스트에 반영되고 (b) 데이터 변경 시 다음 일일 잡(user_embed)에서 재임베딩되며 (c) Chance user_terms 에 가산된다.
- 데모그래픽(user_profiles)은 임베딩/매칭에 미사용(JOIN 없음).
- 스키마 변경 0(마이그레이션 없음).

## Phase 2 범위 밖(후속)

- **Phase 3** — 프론트 프로필 선택 섹션·완성도 미터·`/onboarding`·관심키워드 풀 재설계.
- Sync 점수 공식 자체 개편(임베딩 풍부화로 간접 개선만).
- 비차단 정리(Phase 1 이월): 마이그 COMMENT 하이픈 vs ORM em-dash 통일, upsert echo→재조회, `get_current_user_id` 공용 가드 수렴.
