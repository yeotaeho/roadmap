# SP-3 자기모델 추천 반영 + LLM 설명 레이어 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 자기모델(RIASEC·서사·긍정 근거)을 사용자 임베딩에 직렬화해 Sync/Chance 추천이 코치 대화를 반영하게 하고, 추천 항목별 "왜 이 추천인지" LLM 설명을 일일 배치로 생성해 프론트에 노출한다.

**Architecture:** 스펙 `backend/docs/superpowers/specs/2026-07-02-self-model-recommend-explain-design.md` 기준. (1) `build_user_embed_text` 확장 + 재임베딩 후보를 `users` 기준으로 재구성(코치-only 포함), (2) Gold 두 테이블에 설명 컬럼 + upsert CASE 무효화, (3) `LlmClient.explain_recommendations` + 순수 파서, (4) `RecommendExplainService` 일일 배치(사용자당 LLM 1회), (5) 프론트 서브텍스트 노출.

**Tech Stack:** FastAPI · SQLAlchemy 2.0 async(text SQL) · Alembic · PostgreSQL(Neon) · OpenAI(chat JSON mode) · Next.js/TS.

## Global Constraints

- 한국어 문장 종결은 `.` `?` `!` 만 — `:` 로 끝내지 않는다.
- 새 소스 파일 첫 줄은 한 줄 한국어 역할 주석.
- 커밋은 논리 단위별. `git add .` 금지 — 파일을 명시하고 `.omc/`·`.superpowers/`·`__pycache__` 제외.
- 커밋 메시지 끝에 `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>` 트레일러.
- Alembic 은 `alembic` CLI 직접 실행(`python -m alembic` 아님). **`alembic upgrade head`(Neon 반영)는 사용자 승인 후에만 실행.**
- autogenerate 마이그레이션에서 무관 drift(sectors·sub_sectors·raw_tech_adoption_data·sector_source_map 관련 op) 반드시 제거.
- 백엔드 테스트는 `backend/scripts/*_test.py` 관행(PASS/FAIL check 함수, `python scripts/<name>_test.py`, exit code). pytest 아님. 통합 테스트는 dev Neon 을 쓰므로 시드 데이터는 반드시 cleanup.
- 프론트 검증은 `www.yeotaeho.kr` 에서 `pnpm exec tsc --noEmit` 0 에러.
- 민감 근거(`is_sensitive = true`)는 임베딩 텍스트·LLM 프롬프트 어디에도 넣지 않는다.
- 작업 디렉터리는 `backend/` 기준 명령( `python scripts/...` )이며 PowerShell 에서는 `&&` 대신 `;` 를 쓴다.

---

### Task 1: 임베딩 직렬화 확장 + 재임베딩 후보 재구성(코치-only 포함)

**Files:**
- Modify: `backend/domain/market_insight/hub/services/user_embed_text.py`
- Modify: `backend/domain/market_insight/hub/repositories/embed_repository.py`
- Modify: `backend/domain/market_insight/hub/services/embed_service.py` (`_user_text`·`embed_users`)
- Modify: `backend/domain/market_insight/hub/repositories/chance_repository.py` (`_FETCH_USERS`)
- Test(신규): `backend/scripts/self_model_embed_text_test.py` (순수)
- Test(신규): `backend/scripts/self_model_embed_candidacy_test.py` (Neon 통합)

**Interfaces:**
- Consumes: `user_self_model(user_id, riasec JSONB {"top_codes": [...]}, narrative_summary, updated_at)` · `user_self_model_evidence(user_id, dimension, polarity, content, confidence, is_sensitive, created_at)` (SP-1 기존).
- Produces: `RIASEC_LABEL: dict[str, str]`(공개 — Task 4 재사용) · `self_model_terms(riasec=None, narrative_summary=None, evidence_contents=None) -> list[str]` · `build_user_embed_text(..., riasec=None, narrative_summary=None, evidence_contents=None) -> str`(1000자 캡 내장) · `EmbedRepository.fetch_positive_evidence(user_ids: list, per_user: int = 10) -> dict[str, list[str]]`.

- [ ] **Step 1: 순수 직렬화 실패 테스트 작성**

`backend/scripts/self_model_embed_text_test.py` 생성.

```python
# 자기모델 직렬화(RIASEC 라벨·서사·근거·1000자 캡) 순수 테스트

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from domain.market_insight.hub.services.user_embed_text import (
    MAX_EMBED_TEXT_CHARS,
    RIASEC_LABEL,
    build_user_embed_text,
    self_model_terms,
)

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
    # RIASEC 라벨 — 유효 코드만 한국어 라벨로, 닫힌집합 외 무시
    terms = self_model_terms(riasec={"top_codes": ["I", "A", "X"]})
    check("RIASEC 라벨 변환", terms == [RIASEC_LABEL["I"], RIASEC_LABEL["A"]], str(terms))

    # 비dict riasec·비list top_codes 는 무시
    check("riasec 비정형 무시", self_model_terms(riasec="I") == [], str(self_model_terms(riasec="I")))
    check("top_codes 비정형 무시", self_model_terms(riasec={"top_codes": "I"}) == [])

    # narrative·근거 이어붙임 순서(RIASEC → 서사 → 근거)
    terms = self_model_terms(
        riasec={"top_codes": ["S"]},
        narrative_summary=" 성장을 중시함 ",
        evidence_contents=["발표를 좋아함", "", None],
    )
    check("순서·공백정리", terms == [RIASEC_LABEL["S"], "성장을 중시함", "발표를 좋아함"], str(terms))

    # build_user_embed_text — 기존 프로필 파츠 뒤에 자기모델 파츠
    t = build_user_embed_text(
        target_job="데이터 분석가",
        interest_keywords=["AI"],
        riasec={"top_codes": ["I"]},
        narrative_summary="탐구 지향",
        evidence_contents=["문제 해결을 좋아함"],
    )
    check("직렬화 결합", t == f"데이터 분석가 AI {RIASEC_LABEL['I']} 탐구 지향 문제 해결을 좋아함", t)

    # 기존 호출(자기모델 인자 없음) 하위호환
    check("하위호환", build_user_embed_text(target_job="개발자") == "개발자")

    # 1000자 캡 — 캡 결과가 결정론(해시 안정 전제)
    long_evidence = ["가" * 300, "나" * 300, "다" * 300, "라" * 300]
    t = build_user_embed_text(target_job="개발자", evidence_contents=long_evidence)
    check("1000자 캡", len(t) <= MAX_EMBED_TEXT_CHARS, str(len(t)))
    t2 = build_user_embed_text(target_job="개발자", evidence_contents=long_evidence)
    check("캡 결정론", t == t2)

    # 전부 빈 입력은 기존과 동일하게 "_"
    check("빈 입력 언더스코어", build_user_embed_text() == "_")

    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(run())
```

- [ ] **Step 2: 실패 확인**

Run: `python scripts/self_model_embed_text_test.py` (cwd `backend/`)
Expected: `ImportError: cannot import name 'MAX_EMBED_TEXT_CHARS'` (또는 `RIASEC_LABEL`).

- [ ] **Step 3: `user_embed_text.py` 구현**

파일 상단(라벨 dict 들 아래)에 추가.

```python
MAX_EMBED_TEXT_CHARS = 1000  # 캡 후 텍스트가 해시(source_version) 기준 — 캡으로 잘린 불변 텍스트 재임베딩 방지

RIASEC_LABEL = {
    "R": "현실형",
    "I": "탐구형",
    "A": "예술형",
    "S": "사회형",
    "E": "진취형",
    "C": "관습형",
}
```

`disposition_spec_terms` 아래에 추가.

```python
def self_model_terms(riasec=None, narrative_summary=None, evidence_contents=None) -> list[str]:
    """자기모델(RIASEC 라벨·서사·긍정 근거)을 임베딩용 용어 리스트로 변환한다. 순수·결정론."""
    terms: list[str] = []
    codes = riasec.get("top_codes") if isinstance(riasec, dict) else None
    if isinstance(codes, list):
        terms.extend(RIASEC_LABEL[c] for c in codes if c in RIASEC_LABEL)
    if isinstance(narrative_summary, str) and narrative_summary.strip():
        terms.append(narrative_summary.strip())
    if isinstance(evidence_contents, list):
        terms.extend(str(c).strip() for c in evidence_contents if c and str(c).strip())
    return terms
```

`build_user_embed_text` 를 다음으로 교체(시그니처에 kwargs 3개 추가 + 캡).

```python
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
    riasec=None,
    narrative_summary=None,
    evidence_contents=None,
) -> str:
    """직무+관심키워드+성향+스펙+자기모델을 한 줄 임베딩 텍스트로 직렬화한다. 빈 입력은 '_'."""
    kws = interest_keywords if isinstance(interest_keywords, list) else []
    parts = ([target_job] if target_job else []) + [str(k) for k in kws]
    parts += disposition_spec_terms(
        work_style, company_size_pref, work_type_pref, work_values,
        skills, certifications, languages, projects,
    )
    parts += self_model_terms(riasec, narrative_summary, evidence_contents)
    text = " ".join(p for p in parts if p).strip()
    return text[:MAX_EMBED_TEXT_CHARS].strip() or "_"
```

- [ ] **Step 4: 순수 테스트 통과 확인**

Run: `python scripts/self_model_embed_text_test.py`
Expected: `결과: PASS=9 FAIL=0`, exit 0.

- [ ] **Step 5: `embed_repository.py` — 후보 쿼리 재구성 + 긍정 근거 조회**

import 에 `bindparam` 추가.

```python
from sqlalchemy import bindparam, text
```

`_FETCH_UNEMBEDDED_USERS` 를 다음으로 교체.

```python
# 임베딩 후보 — users 기준. 프로필이 없어도 자기모델·비민감 근거가 있으면 후보(코치-only 포함).
# 타임스탬프 비교에 자기모델 갱신·근거 추가를 포함해 코치 대화가 재임베딩을 트리거한다.
_FETCH_UNEMBEDDED_USERS = text(
    """
    SELECT u.id AS user_id, p.target_job, p.interest_keywords,
           pref.work_style, pref.company_size_pref, pref.work_type_pref, pref.work_values,
           per.skills, per.certifications, per.languages, per.projects,
           sm.riasec, sm.narrative_summary,
           e.source_version
    FROM users u
    LEFT JOIN user_sync_profiles p ON p.user_id = u.id
    LEFT JOIN user_preferences pref ON pref.user_id = u.id
    LEFT JOIN user_personas per ON per.user_id = u.id
    LEFT JOIN user_self_model sm ON sm.user_id = u.id
    LEFT JOIN (
        SELECT user_id, max(created_at) AS last_evidence_at
        FROM user_self_model_evidence
        WHERE is_sensitive = false
        GROUP BY user_id
    ) ev ON ev.user_id = u.id
    LEFT JOIN user_embeddings e ON e.user_id = u.id AND e.embedding_model = :model
    WHERE (p.user_id IS NOT NULL OR sm.user_id IS NOT NULL OR ev.user_id IS NOT NULL)
      AND (
        e.user_id IS NULL
        OR GREATEST(
             COALESCE(p.updated_at, to_timestamp(0)),
             COALESCE(pref.updated_at, to_timestamp(0)),
             COALESCE(per.updated_at, to_timestamp(0)),
             COALESCE(sm.updated_at, to_timestamp(0)),
             COALESCE(ev.last_evidence_at, to_timestamp(0))
           ) > e.computed_at
      )
    LIMIT :lim
    """
)

# 임베딩용 비민감·긍정 근거 — 사용자별 confidence·최신순 상위 N. dislike/constraint/민감 제외.
_FETCH_POSITIVE_EVIDENCE = text(
    """
    SELECT user_id, content FROM (
        SELECT user_id, content,
               ROW_NUMBER() OVER (
                   PARTITION BY user_id
                   ORDER BY confidence DESC NULLS LAST, created_at DESC, id DESC
               ) AS rn
        FROM user_self_model_evidence
        WHERE user_id IN :uids
          AND is_sensitive = false
          AND dimension IN ('like', 'value', 'aspiration', 'skill_signal')
          AND (polarity IS NULL OR polarity <> 'dislike')
    ) t
    WHERE rn <= :per_user
    ORDER BY user_id, rn
    """
).bindparams(bindparam("uids", expanding=True))
```

`EmbedRepository` 클래스에 메서드 추가.

```python
    async def fetch_positive_evidence(self, user_ids: list, per_user: int = 10) -> dict[str, list[str]]:
        """사용자별 임베딩용 비민감·긍정 근거 content 목록. {str(user_id): [content...]}."""
        if not user_ids:
            return {}
        rows = (
            await self.session.execute(
                _FETCH_POSITIVE_EVIDENCE,
                {"uids": [str(u) for u in user_ids], "per_user": per_user},
            )
        ).all()
        out: dict[str, list[str]] = {}
        for r in rows:
            out.setdefault(str(r.user_id), []).append(r.content)
        return out
```

- [ ] **Step 6: `embed_service.py` — 자기모델 파츠 전달**

`_user_text` 시그니처·본문을 다음으로 교체.

```python
    @staticmethod
    def _user_text(
        target_job, interest_keywords, work_style=None, company_size_pref=None,
        work_type_pref=None, work_values=None, skills=None, certifications=None,
        languages=None, projects=None, riasec=None, narrative_summary=None,
        evidence_contents=None,
    ) -> str:
        return build_user_embed_text(
            target_job, interest_keywords, work_style, company_size_pref, work_type_pref,
            work_values, skills, certifications, languages, projects,
            riasec=riasec, narrative_summary=narrative_summary,
            evidence_contents=evidence_contents,
        )
```

`embed_users` 의 for 루프 앞에 근거 로드를 추가하고 `_user_text` 호출을 교체.

```python
    async def embed_users(self, limit: int = DEFAULT_LIMIT) -> dict:
        rows = await self.repo.fetch_unembedded_users(self._model, limit)
        evidence_map = await self.repo.fetch_positive_evidence([r.user_id for r in rows])
        # 텍스트·해시 산출 후, 저장된 해시와 동일하면(타임스탬프상 후보지만 내용 불변) 임베딩 생략.
        pending = []
        for r in rows:
            t = self._user_text(
                r.target_job, r.interest_keywords,
                r.work_style, r.company_size_pref, r.work_type_pref, r.work_values,
                r.skills, r.certifications, r.languages, r.projects,
                riasec=r.riasec, narrative_summary=r.narrative_summary,
                evidence_contents=evidence_map.get(str(r.user_id)),
            )
            version = hashlib.sha256(t.encode("utf-8")).hexdigest()[:16]
            if version != r.source_version:
                pending.append((r.user_id, t, version))
```

(이후 배치 임베딩·upsert 루프는 기존 그대로.)

- [ ] **Step 7: `chance_repository.py` — 매칭 사용자 확장**

`_FETCH_USERS` 를 다음으로 교체.

```python
# 매칭용 사용자 — users 기준. 프로필이 없어도 자기모델·비민감 근거가 있으면 포함(코치-only).
_FETCH_USERS = text(
    """
    SELECT u.id AS user_id, p.target_job, p.interest_keywords,
           pref.work_style, pref.company_size_pref, pref.work_type_pref, pref.work_values,
           per.skills, per.certifications, per.languages, per.projects
    FROM users u
    LEFT JOIN user_sync_profiles p ON p.user_id = u.id
    LEFT JOIN user_preferences pref ON pref.user_id = u.id
    LEFT JOIN user_personas per ON per.user_id = u.id
    LEFT JOIN user_self_model sm ON sm.user_id = u.id
    WHERE p.user_id IS NOT NULL OR sm.user_id IS NOT NULL
       OR EXISTS (
            SELECT 1 FROM user_self_model_evidence ev
            WHERE ev.user_id = u.id AND ev.is_sensitive = false
          )
    """
)
```

주의 — `ChanceMatchService.match_all` 은 `u.target_job`·`u.interest_keywords` 가 None 이어도 기존 분기(`isinstance` 검사·빈 user_terms 시 semantic-only)로 동작한다. 서비스 코드는 수정하지 않는다.

- [ ] **Step 8: 통합(후보·필터) 실패 테스트 작성**

`backend/scripts/self_model_embed_candidacy_test.py` 생성.

```python
# 재임베딩 후보 — 코치-only 사용자 포함·자기모델 갱신 트리거·긍정 근거 필터 (Neon 통합)

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

from sqlalchemy import text

from core.config.settings import get_settings
from core.database import AsyncSessionLocal
from domain.market_insight.hub.repositories.chance_repository import ChanceRepository
from domain.market_insight.hub.repositories.embed_repository import EmbedRepository

PASS = 0
FAIL = 0
TEST_EMAIL = "sp3-candidacy-test@example.local"


def check(n: str, c: bool, e: str = "") -> None:
    global PASS, FAIL
    if c:
        PASS += 1
        print(f"[PASS] {n}")
    else:
        FAIL += 1
        print(f"[FAIL] {n} {e}")


async def _cleanup(s, uid: str | None) -> None:
    if uid is None:
        r = (await s.execute(text("SELECT id FROM users WHERE email = :e"), {"e": TEST_EMAIL})).first()
        if r is None:
            return
        uid = str(r.id)
    await s.execute(text("DELETE FROM user_self_model_evidence WHERE user_id = CAST(:u AS UUID)"), {"u": uid})
    await s.execute(text("DELETE FROM user_self_model WHERE user_id = CAST(:u AS UUID)"), {"u": uid})
    await s.execute(text("DELETE FROM user_embeddings WHERE user_id = CAST(:u AS UUID)"), {"u": uid})
    await s.execute(text("DELETE FROM users WHERE id = CAST(:u AS UUID)"), {"u": uid})
    await s.commit()


async def run() -> int:
    model = get_settings().llm_embed_model
    async with AsyncSessionLocal() as s:
        await _cleanup(s, None)
        # 프로필 없는 코치-only 사용자 생성
        uid = str((await s.execute(text(
            "INSERT INTO users (email, nickname) VALUES (:e, 'SP3테스트') RETURNING id"
        ), {"e": TEST_EMAIL})).scalar_one())
        await s.commit()

        repo = EmbedRepository(s)

        # 자기모델도 근거도 없으면 후보 아님
        rows = await repo.fetch_unembedded_users(model, 1000)
        check("신호 없는 사용자 제외", uid not in {str(r.user_id) for r in rows})

        # 자기모델만 생기면 후보 진입(프로필 없음)
        await s.execute(text(
            "INSERT INTO user_self_model (user_id, riasec, narrative_summary, source, updated_at) "
            "VALUES (CAST(:u AS UUID), CAST(:r AS JSONB), '탐구 지향', 'coach_extraction', now())"
        ), {"u": uid, "r": '{"top_codes": ["I"]}'})
        await s.commit()
        rows = await repo.fetch_unembedded_users(model, 1000)
        mine = [r for r in rows if str(r.user_id) == uid]
        check("코치-only 후보 진입", len(mine) == 1, str(len(mine)))
        check("riasec 셀렉트 포함", mine and mine[0].riasec == {"top_codes": ["I"]}, str(mine and mine[0].riasec))
        check("narrative 셀렉트 포함", mine and mine[0].narrative_summary == "탐구 지향")

        # 임베딩 기록 후 후보에서 빠짐 → 자기모델 갱신 시 재진입
        await repo.upsert_user_embedding(uid, [0.0] * 3072, "deadbeefdeadbeef", model)
        await s.commit()
        rows = await repo.fetch_unembedded_users(model, 1000)
        check("임베딩 후 후보 제외", uid not in {str(r.user_id) for r in rows})
        await s.execute(text(
            "UPDATE user_self_model SET narrative_summary = '성장 지향', updated_at = now() "
            "WHERE user_id = CAST(:u AS UUID)"), {"u": uid})
        await s.commit()
        rows = await repo.fetch_unembedded_users(model, 1000)
        check("자기모델 갱신 → 재진입", uid in {str(r.user_id) for r in rows})

        # 긍정 근거 필터 — dislike·constraint·민감 제외
        for dim, pol, content, sens in [
            ("like", "like", "발표를 좋아함", False),
            ("value", None, "성장을 중시함", False),
            ("dislike", "dislike", "야근을 싫어함", False),
            ("constraint", None, "장거리 통근 불가", False),
            ("like", "like", "민감한 내용", True),
        ]:
            await s.execute(text(
                "INSERT INTO user_self_model_evidence "
                "(user_id, dimension, polarity, content, confidence, is_sensitive, content_hash, source) "
                "VALUES (CAST(:u AS UUID), :d, :p, :c, 0.9, :s, md5(:d || COALESCE(:p,'') || :c), 'coach_extraction')"
            ), {"u": uid, "d": dim, "p": pol, "c": content, "s": sens})
        await s.commit()
        ev = await repo.fetch_positive_evidence([uid])
        contents = ev.get(uid, [])
        check("긍정 근거 포함", "발표를 좋아함" in contents and "성장을 중시함" in contents, str(contents))
        check("dislike 제외", "야근을 싫어함" not in contents)
        check("constraint 제외", "장거리 통근 불가" not in contents)
        check("민감 제외", "민감한 내용" not in contents)
        check("빈 입력 빈 dict", await repo.fetch_positive_evidence([]) == {})

        # Chance 매칭 사용자에도 코치-only 포함
        users = await ChanceRepository(s).fetch_users()
        check("chance 사용자 포함", uid in {str(r.user_id) for r in users})

        await _cleanup(s, uid)
    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
```

- [ ] **Step 9: 통합 테스트 실행·통과 확인**

Run: `python scripts/self_model_embed_candidacy_test.py`
Expected: `결과: PASS=12 FAIL=0`, exit 0. (Step 5~7 구현이 이미 되어 있으므로 바로 통과해야 한다. 실패하면 SQL 을 수정한다.)

- [ ] **Step 10: 기존 회귀 실행**

Run: `python scripts/user_embed_text_test.py; python scripts/user_reembed_test.py; python scripts/chance_user_terms_test.py; python scripts/embed_helpers_test.py`
Expected: 각 스크립트 FAIL=0. (`user_reembed_test.py` 는 프로필 보유 사용자의 기존 후보 동작이 유지되는지 검증한다.)

- [ ] **Step 11: 커밋**

```bash
git add backend/domain/market_insight/hub/services/user_embed_text.py backend/domain/market_insight/hub/repositories/embed_repository.py backend/domain/market_insight/hub/services/embed_service.py backend/domain/market_insight/hub/repositories/chance_repository.py backend/scripts/self_model_embed_text_test.py backend/scripts/self_model_embed_candidacy_test.py
git commit -m "feat(sp3): 자기모델을 사용자 임베딩에 직렬화 + 코치-only 사용자 추천 후보 포함"
```

---

### Task 2: 설명 컬럼 마이그레이션 + upsert CASE 무효화 + 서빙 노출

**Files:**
- Modify: `backend/domain/market_insight/models/bases/sync_scores_daily.py`
- Modify: `backend/domain/market_insight/models/bases/user_chance_matches.py`
- Create: `backend/alembic/versions/<autogen>_add_explanation_to_sync_chance_gold.py`
- Modify: `backend/domain/market_insight/hub/repositories/sync_repository.py` (`_UPSERT_SYNC_GOLD`·`_FETCH_SCORES`·`fetch_scores`)
- Modify: `backend/domain/market_insight/hub/repositories/chance_repository.py` (`_UPSERT_MATCH`·`_FETCH_MATCHES`·`fetch_matches`)
- Modify: `backend/docs/erd.md` (sync_scores_daily·user_chance_matches 컬럼 반영)
- Test(신규): `backend/scripts/explanation_invalidation_test.py` (Neon 통합)

**Interfaces:**
- Consumes: 없음(독립).
- Produces: `sync_scores_daily.explanation TEXT NULL` · `user_chance_matches.match_explanation TEXT NULL` · upsert 시 "입력 불변이면 설명 보존, 변경이면 NULL" 시맨틱 · `fetch_scores()` dict 에 `explanation` 키 · `fetch_matches()` dict 에 `match_explanation` 키(라우터는 dict 통과라 API 자동 노출).

- [ ] **Step 1: ORM 컬럼 추가**

`sync_scores_daily.py` — import 의 `String,` 뒤에 `Text,` 추가(알파벳순 유지), `badge` 필드 아래에 추가.

```python
    explanation: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="LLM 생성 추천 설명(없으면 결정론 폴백 표시)"
    )
```

`user_chance_matches.py` — 동일하게 import 에 `Text,` 추가, `match_reason` 필드 아래에 추가.

```python
    match_explanation: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="LLM 생성 매칭 설명(match_reason 은 결정론 폴백)"
    )
```

- [ ] **Step 2: 마이그레이션 autogenerate·drift 제거**

Run: `alembic revision --autogenerate -m "add explanation columns to sync chance gold"` (cwd `backend/`)

생성 파일을 열어 `op.add_column("sync_scores_daily", ...)`·`op.add_column("user_chance_matches", ...)` 2개와 대응 downgrade 2개만 남기고, sectors·sub_sectors·raw_tech_adoption_data·sector_source_map 등 무관 drift op 를 전부 삭제한다.

- [ ] **Step 3: 마이그레이션 적용 (사용자 승인 게이트)**

**사용자에게 Neon 반영 승인을 받은 뒤** 실행한다.

Run: `alembic upgrade head`
Expected: 에러 없이 완료. `alembic current` 가 새 revision 을 가리킨다.

- [ ] **Step 4: upsert CASE + 서빙 SQL 수정**

`sync_repository.py` — `_UPSERT_SYNC_GOLD` 를 다음으로 교체.

```python
_UPSERT_SYNC_GOLD = text(
    """
    INSERT INTO sync_scores_daily (user_id, sector_slug, recorded_date, score, badge)
    VALUES (:user_id, :sector_slug, CURRENT_DATE, :score, :badge)
    ON CONFLICT (user_id, sector_slug, recorded_date) DO UPDATE SET
        score = EXCLUDED.score,
        badge = EXCLUDED.badge,
        explanation = CASE
            WHEN sync_scores_daily.score = EXCLUDED.score
             AND sync_scores_daily.badge IS NOT DISTINCT FROM EXCLUDED.badge
            THEN sync_scores_daily.explanation ELSE NULL END
    """
)
```

`_FETCH_SCORES` 의 SELECT 목록에 `d.explanation,` 을 `d.badge,` 뒤에 추가하고, `fetch_scores` 의 dict 에 `"explanation": r.explanation,` 을 `"badge"` 뒤에 추가.

`chance_repository.py` — `_UPSERT_MATCH` 를 다음으로 교체.

```python
_UPSERT_MATCH = text(
    """
    INSERT INTO user_chance_matches (user_id, opportunity_id, match_score, match_reason, updated_at)
    VALUES (:user_id, :opportunity_id, :match_score, :match_reason, now())
    ON CONFLICT (user_id, opportunity_id) DO UPDATE SET
        match_score = EXCLUDED.match_score,
        match_reason = EXCLUDED.match_reason,
        match_explanation = CASE
            WHEN user_chance_matches.match_score IS NOT DISTINCT FROM EXCLUDED.match_score
             AND user_chance_matches.match_reason IS NOT DISTINCT FROM EXCLUDED.match_reason
            THEN user_chance_matches.match_explanation ELSE NULL END,
        updated_at = now()
    """
)
```

`_FETCH_MATCHES` 의 SELECT 목록에 `m.match_explanation,` 을 `m.match_reason,` 뒤에 추가하고, `fetch_matches` 의 dict 에 `"match_explanation": r.match_explanation,` 을 `"match_reason"` 뒤에 추가.

- [ ] **Step 5: CASE 보존·무효화 통합 테스트 작성**

`backend/scripts/explanation_invalidation_test.py` 생성.

```python
# 설명 무효화 — upsert 시 입력 불변이면 설명 보존, 변경이면 NULL (Neon 통합)

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

from sqlalchemy import text

from core.database import AsyncSessionLocal
from domain.market_insight.hub.repositories.chance_repository import ChanceRepository
from domain.market_insight.hub.repositories.sync_repository import SyncRepository

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


async def run() -> int:
    async with AsyncSessionLocal() as s:
        uid = str((await s.execute(text("SELECT id FROM users ORDER BY created_at LIMIT 1"))).scalar_one())
        slug = (await s.execute(text("SELECT slug FROM sectors ORDER BY slug LIMIT 1"))).scalar_one()
        opp = (await s.execute(text(
            "SELECT id FROM chance_opportunities WHERE is_active = true ORDER BY id LIMIT 1"
        ))).scalar_one()

        # 시드 정리(재실행 안전)
        await s.execute(text(
            "DELETE FROM sync_scores_daily WHERE user_id = CAST(:u AS UUID) "
            "AND sector_slug = :sl AND recorded_date = CURRENT_DATE"), {"u": uid, "sl": slug})
        await s.execute(text(
            "DELETE FROM user_chance_matches WHERE user_id = CAST(:u AS UUID) AND opportunity_id = :o"
        ), {"u": uid, "o": opp})
        await s.commit()

        sync_repo = SyncRepository(s)
        chance_repo = ChanceRepository(s)

        # Sync — 설명 부여 후 동일 upsert 는 보존, 점수 변경은 NULL
        await sync_repo.upsert_sync_gold(uid, slug, 72, "적합")
        await s.execute(text(
            "UPDATE sync_scores_daily SET explanation = '테스트 설명' "
            "WHERE user_id = CAST(:u AS UUID) AND sector_slug = :sl AND recorded_date = CURRENT_DATE"
        ), {"u": uid, "sl": slug})
        await s.commit()
        await sync_repo.upsert_sync_gold(uid, slug, 72, "적합")
        await s.commit()
        v = (await s.execute(text(
            "SELECT explanation FROM sync_scores_daily WHERE user_id = CAST(:u AS UUID) "
            "AND sector_slug = :sl AND recorded_date = CURRENT_DATE"), {"u": uid, "sl": slug})).scalar_one()
        check("sync 불변 → 설명 보존", v == "테스트 설명", str(v))
        await sync_repo.upsert_sync_gold(uid, slug, 80, "강한 적합")
        await s.commit()
        v = (await s.execute(text(
            "SELECT explanation FROM sync_scores_daily WHERE user_id = CAST(:u AS UUID) "
            "AND sector_slug = :sl AND recorded_date = CURRENT_DATE"), {"u": uid, "sl": slug})).scalar_one()
        check("sync 변경 → 설명 NULL", v is None, str(v))

        # fetch_scores 에 explanation 키 노출
        scores = await sync_repo.fetch_scores(uid)
        check("fetch_scores 키", all("explanation" in r for r in scores), str(scores[:1]))

        # Chance — 동일 패턴
        await chance_repo.upsert_match(uid, opp, 80, "테스트 사유")
        await s.execute(text(
            "UPDATE user_chance_matches SET match_explanation = '매칭 설명' "
            "WHERE user_id = CAST(:u AS UUID) AND opportunity_id = :o"), {"u": uid, "o": opp})
        await s.commit()
        await chance_repo.upsert_match(uid, opp, 80, "테스트 사유")
        await s.commit()
        v = (await s.execute(text(
            "SELECT match_explanation FROM user_chance_matches "
            "WHERE user_id = CAST(:u AS UUID) AND opportunity_id = :o"), {"u": uid, "o": opp})).scalar_one()
        check("chance 불변 → 설명 보존", v == "매칭 설명", str(v))
        await chance_repo.upsert_match(uid, opp, 55, "다른 사유")
        await s.commit()
        v = (await s.execute(text(
            "SELECT match_explanation FROM user_chance_matches "
            "WHERE user_id = CAST(:u AS UUID) AND opportunity_id = :o"), {"u": uid, "o": opp})).scalar_one()
        check("chance 변경 → 설명 NULL", v is None, str(v))

        matches = await chance_repo.fetch_matches(uid)
        check("fetch_matches 키", all("match_explanation" in r for r in matches), str(matches[:1]))

        # 시드 정리
        await s.execute(text(
            "DELETE FROM sync_scores_daily WHERE user_id = CAST(:u AS UUID) "
            "AND sector_slug = :sl AND recorded_date = CURRENT_DATE"), {"u": uid, "sl": slug})
        await s.execute(text(
            "DELETE FROM user_chance_matches WHERE user_id = CAST(:u AS UUID) AND opportunity_id = :o"
        ), {"u": uid, "o": opp})
        await s.commit()
    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
```

- [ ] **Step 6: 테스트 실행**

Run: `python scripts/explanation_invalidation_test.py`
Expected: `결과: PASS=6 FAIL=0`, exit 0.

- [ ] **Step 7: ERD 반영**

`backend/docs/erd.md` 에서 `sync_scores_daily` 정의에 `explanation TEXT NULL — LLM 추천 설명(입력 변경 시 NULL 무효화)`, `user_chance_matches` 정의에 `match_explanation TEXT NULL — LLM 매칭 설명(match_reason 은 결정론 폴백)` 행을 추가한다. 해당 테이블 정의 섹션의 기존 표기 형식을 그대로 따른다.

- [ ] **Step 8: 커밋**

```bash
git add backend/domain/market_insight/models/bases/sync_scores_daily.py backend/domain/market_insight/models/bases/user_chance_matches.py backend/alembic/versions/<생성된파일>.py backend/domain/market_insight/hub/repositories/sync_repository.py backend/domain/market_insight/hub/repositories/chance_repository.py backend/docs/erd.md backend/scripts/explanation_invalidation_test.py
git commit -m "feat(sp3): Sync/Chance Gold 설명 컬럼 + upsert 불변 보존·변경 무효화 + 서빙 노출"
```

---

### Task 3: `LlmClient.explain_recommendations` + 순수 파서

**Files:**
- Modify: `backend/core/llm/client.py`
- Test(신규): `backend/scripts/recommend_explain_parse_test.py` (순수)

**Interfaces:**
- Consumes: 없음(독립). 기존 `LlmClient` 의 chat JSON-mode 관행(`response_format={"type": "json_object"}`)을 따른다.
- Produces: `_parse_recommend_explain(raw: str | None, valid_slugs: list[str], valid_opp_ids: list[int]) -> {"sync": [{"sector_slug", "text"}], "chance": [{"opportunity_id", "text"}]}` · `LlmClient.explain_recommendations(user_context: dict, sync_items: list[dict], chance_items: list[dict]) -> 같은 형태` · `_EXPLAIN_TEXT_MAX = 200`.

- [ ] **Step 1: 파서 실패 테스트 작성**

`backend/scripts/recommend_explain_parse_test.py` 생성.

```python
# 추천 설명 파서 — 닫힌 slug/id 검증·200자 클램프·실패 시 빈 리스트 (순수)

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.llm.client import _EXPLAIN_TEXT_MAX, _parse_recommend_explain

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
    slugs = ["ai-software", "bio-health"]
    ids = [10, 20]

    ok = json.dumps({
        "sync": [
            {"sector_slug": "ai-software", "text": " 관심 키워드와 정렬돼요. "},
            {"sector_slug": "unknown", "text": "버려야 함"},
            {"sector_slug": "bio-health", "text": ""},
        ],
        "chance": [
            {"opportunity_id": 10, "text": "포부와 맞닿아 있어요."},
            {"opportunity_id": 99, "text": "버려야 함"},
            {"opportunity_id": "20", "text": "문자열 id 버림"},
        ],
    }, ensure_ascii=False)
    r = _parse_recommend_explain(ok, slugs, ids)
    check("유효 sync 1건", r["sync"] == [{"sector_slug": "ai-software", "text": "관심 키워드와 정렬돼요."}], str(r["sync"]))
    check("유효 chance 1건", r["chance"] == [{"opportunity_id": 10, "text": "포부와 맞닿아 있어요."}], str(r["chance"]))

    # 중복 slug/id 는 첫 항목만
    dup = json.dumps({"sync": [
        {"sector_slug": "ai-software", "text": "첫째"},
        {"sector_slug": "ai-software", "text": "둘째"},
    ], "chance": []})
    check("중복 slug 첫 항목", _parse_recommend_explain(dup, slugs, ids)["sync"] == [{"sector_slug": "ai-software", "text": "첫째"}])

    # 200자 클램프
    long = json.dumps({"sync": [{"sector_slug": "ai-software", "text": "가" * 500}], "chance": []})
    r = _parse_recommend_explain(long, slugs, ids)
    check("클램프", len(r["sync"][0]["text"]) == _EXPLAIN_TEXT_MAX, str(len(r["sync"][0]["text"])))

    # 비JSON·비dict·None → 빈 결과
    check("비JSON", _parse_recommend_explain("응 안돼", slugs, ids) == {"sync": [], "chance": []})
    check("배열 루트", _parse_recommend_explain("[]", slugs, ids) == {"sync": [], "chance": []})
    check("None", _parse_recommend_explain(None, slugs, ids) == {"sync": [], "chance": []})

    # sync/chance 키 비list·항목 비dict 허용 처리
    weird = json.dumps({"sync": "x", "chance": [1, {"opportunity_id": 20, "text": "유효"}]})
    r = _parse_recommend_explain(weird, slugs, ids)
    check("비정형 관용", r == {"sync": [], "chance": [{"opportunity_id": 20, "text": "유효"}]}, str(r))

    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(run())
```

- [ ] **Step 2: 실패 확인**

Run: `python scripts/recommend_explain_parse_test.py`
Expected: `ImportError: cannot import name '_parse_recommend_explain'`.

- [ ] **Step 3: `client.py` 구현**

`_SELF_MODEL_EXTRACT_SYSTEM_PROMPT` 정의 아래에 프롬프트·상수·파서를 추가.

```python
_RECOMMEND_EXPLAIN_SYSTEM_PROMPT = (
    "너는 청년 진로 내비게이터의 추천 설명가다. 사용자 컨텍스트(직무·관심·자기모델: 성향 라벨·서사·"
    "좋아하는 것 positives·회피하는 것 dislikes)와 추천 항목별 결정론 지표(점수·적합도·트렌드·매칭 사유)를 받아, "
    "항목마다 '왜 이 추천인지'를 존댓말 1~2문장으로 쓴다. 입력에 주어진 사실만 사용하고 새 사실을 지어내지 마라. "
    "dislikes 와 명확히 충돌하는 항목은 문장 안에 짧은 주의를 포함하라(점수 언급은 선택). "
    'JSON 객체만 출력하라. 형식: {"sync": [{"sector_slug": <입력에 있던 slug>, "text": <설명>}], '
    '"chance": [{"opportunity_id": <입력에 있던 정수 id>, "text": <설명>}]}. 입력에 없는 slug·id 를 만들지 마라.'
)

_EXPLAIN_TEXT_MAX = 200


def _parse_recommend_explain(
    raw: str | None, valid_slugs: list[str], valid_opp_ids: list[int]
) -> dict:
    """추천 설명 응답을 검증된 {sync, chance} 로 파싱한다. 무네트워크 순수 함수.

    모르는 slug/id·빈 text·중복은 버리고 text 는 200자 클램프. 실패 시 빈 리스트(쓰기 없음 → 다음날 재시도).
    """
    empty: dict = {"sync": [], "chance": []}
    try:
        obj = json.loads(raw) if raw else {}
    except (json.JSONDecodeError, TypeError):
        return {"sync": [], "chance": []}
    if not isinstance(obj, dict):
        return empty

    slugs = set(valid_slugs)
    sync_out: list[dict] = []
    seen_slugs: set[str] = set()
    sync_raw = obj.get("sync")
    for it in sync_raw if isinstance(sync_raw, list) else []:
        if not isinstance(it, dict):
            continue
        slug = it.get("sector_slug")
        text_v = it.get("text")
        if slug in slugs and slug not in seen_slugs and isinstance(text_v, str) and text_v.strip():
            seen_slugs.add(slug)
            sync_out.append({"sector_slug": slug, "text": text_v.strip()[:_EXPLAIN_TEXT_MAX]})

    opp_ids = set(valid_opp_ids)
    chance_out: list[dict] = []
    seen_ids: set[int] = set()
    chance_raw = obj.get("chance")
    for it in chance_raw if isinstance(chance_raw, list) else []:
        if not isinstance(it, dict):
            continue
        oid = it.get("opportunity_id")
        text_v = it.get("text")
        if (
            isinstance(oid, int) and not isinstance(oid, bool)
            and oid in opp_ids and oid not in seen_ids
            and isinstance(text_v, str) and text_v.strip()
        ):
            seen_ids.add(oid)
            chance_out.append({"opportunity_id": oid, "text": text_v.strip()[:_EXPLAIN_TEXT_MAX]})

    return {"sync": sync_out, "chance": chance_out}
```

`LlmClient` 클래스의 `extract_self_model` 메서드 아래에 추가.

```python
    async def explain_recommendations(
        self, user_context: dict, sync_items: list[dict], chance_items: list[dict]
    ) -> dict:
        """사용자 컨텍스트+추천 항목 결정론 지표에서 항목별 자연어 설명을 생성한다."""
        payload = json.dumps(
            {"user": user_context, "sync": sync_items, "chance": chance_items},
            ensure_ascii=False, default=str,
        )
        resp = await self._client.chat.completions.create(
            model=self._model,
            temperature=0.3,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _RECOMMEND_EXPLAIN_SYSTEM_PROMPT},
                {"role": "user", "content": payload},
            ],
        )
        return _parse_recommend_explain(
            resp.choices[0].message.content,
            [i["sector_slug"] for i in sync_items],
            [i["opportunity_id"] for i in chance_items],
        )
```

- [ ] **Step 4: 파서 테스트 통과 확인**

Run: `python scripts/recommend_explain_parse_test.py`
Expected: `결과: PASS=8 FAIL=0`, exit 0.

- [ ] **Step 5: 커밋**

```bash
git add backend/core/llm/client.py backend/scripts/recommend_explain_parse_test.py
git commit -m "feat(sp3): LlmClient.explain_recommendations + 닫힌 스키마 파서"
```

---

### Task 4: RecommendExplainService 일일 배치 + 스케줄러 등록

**Files:**
- Create: `backend/domain/market_insight/hub/repositories/recommend_explain_repository.py`
- Create: `backend/domain/market_insight/hub/services/recommend_explain_service.py`
- Modify: `backend/core/scheduler.py` (`_job_recommend_explain` + `_REFINE_PIPELINE` 등록)
- Test(신규): `backend/scripts/recommend_explain_service_test.py` (Neon + FakeLLM)
- Test(신규): `backend/scripts/recommend_explain_job_test.py` (배선 스모크 — LLM 무호출)

**Interfaces:**
- Consumes: Task 2 의 `explanation`/`match_explanation` 컬럼, Task 3 의 `LlmClient.explain_recommendations`, Task 1 의 `RIASEC_LABEL`.
- Produces: `RecommendExplainService.explain_pending(limit=200) -> {"users", "processed", "failed", "written"} | {"skipped": True, ...}` · `_build_user_context(ctx_row, evidence) -> dict`(순수) · 스케줄러 `_job_recommend_explain`, `_REFINE_PIPELINE` 마지막 스텝 `"recommend_explain"`.

- [ ] **Step 1: 리포지토리 작성**

`backend/domain/market_insight/hub/repositories/recommend_explain_repository.py` 생성.

```python
# 추천 설명 리포지토리 — 설명 없는 Sync/Chance 상위 행·사용자 컨텍스트 조회, 설명 기록

from __future__ import annotations

from sqlalchemy import bindparam, text

from domain.auth.hub.repositories.base_repository import BaseRepository

# 오늘 설명 없는 Sync 상위 행 — 사용자별 점수순 상위 N, '데이터 부족' 배지는 설명할 신호가 없어 제외.
_FETCH_UNEXPLAINED_SYNC = text(
    """
    SELECT user_id, sector_slug, sector_name, score, badge, affinity_score, trend_score FROM (
        SELECT d.user_id, d.sector_slug, s.name_ko AS sector_name, d.score, d.badge,
               i.affinity_score, i.trend_score,
               ROW_NUMBER() OVER (
                   PARTITION BY d.user_id ORDER BY d.score DESC, d.sector_slug
               ) AS rn
        FROM sync_scores_daily d
        JOIN sectors s ON s.slug = d.sector_slug
        LEFT JOIN refined_sync_inputs i
               ON i.user_id = d.user_id AND i.sector_slug = d.sector_slug
              AND i.reference_date = d.recorded_date
        WHERE d.recorded_date = CURRENT_DATE
          AND d.explanation IS NULL
          AND d.badge IS DISTINCT FROM :insufficient
    ) t
    WHERE rn <= :per_user
    """
)

# 설명 없는 Chance 매치 — 사용자별 점수순 상위 N, 활성·미마감 공고만.
_FETCH_UNEXPLAINED_MATCHES = text(
    """
    SELECT user_id, opportunity_id, match_score, match_reason, title, opportunity_type FROM (
        SELECT m.user_id, m.opportunity_id, m.match_score, m.match_reason,
               o.title, o.opportunity_type,
               ROW_NUMBER() OVER (
                   PARTITION BY m.user_id ORDER BY m.match_score DESC NULLS LAST, m.opportunity_id
               ) AS rn
        FROM user_chance_matches m
        JOIN chance_opportunities o ON o.id = m.opportunity_id
        WHERE m.match_explanation IS NULL
          AND o.is_active = true
          AND (o.d_day_date IS NULL OR o.d_day_date >= CURRENT_DATE)
    ) t
    WHERE rn <= :per_user
    """
)

_FETCH_USER_CONTEXT = text(
    """
    SELECT u.id AS user_id, p.target_job, p.interest_keywords,
           sm.riasec, sm.narrative_summary
    FROM users u
    LEFT JOIN user_sync_profiles p ON p.user_id = u.id
    LEFT JOIN user_self_model sm ON sm.user_id = u.id
    WHERE u.id IN :uids
    """
).bindparams(bindparam("uids", expanding=True))

# 프롬프트용 비민감 근거 — 긍정/회피 분리는 서비스에서 수행(민감은 어떤 경우에도 미주입).
_FETCH_CONTEXT_EVIDENCE = text(
    """
    SELECT user_id, dimension, polarity, content
    FROM user_self_model_evidence
    WHERE user_id IN :uids
      AND is_sensitive = false
      AND dimension IN ('like', 'dislike', 'value', 'aspiration', 'skill_signal')
    ORDER BY user_id, confidence DESC NULLS LAST, created_at DESC, id DESC
    """
).bindparams(bindparam("uids", expanding=True))

_UPDATE_SYNC_EXPLANATION = text(
    """
    UPDATE sync_scores_daily SET explanation = :explanation
    WHERE user_id = CAST(:user_id AS UUID) AND sector_slug = :sector_slug
      AND recorded_date = CURRENT_DATE
    """
)

_UPDATE_MATCH_EXPLANATION = text(
    """
    UPDATE user_chance_matches SET match_explanation = :explanation
    WHERE user_id = CAST(:user_id AS UUID) AND opportunity_id = :opportunity_id
    """
)


class RecommendExplainRepository(BaseRepository):
    async def fetch_unexplained_sync(self, per_user: int, insufficient_badge: str) -> list:
        return list(
            (
                await self.session.execute(
                    _FETCH_UNEXPLAINED_SYNC,
                    {"per_user": per_user, "insufficient": insufficient_badge},
                )
            ).all()
        )

    async def fetch_unexplained_matches(self, per_user: int) -> list:
        return list(
            (await self.session.execute(_FETCH_UNEXPLAINED_MATCHES, {"per_user": per_user})).all()
        )

    async def fetch_user_context(self, user_ids: list[str]) -> dict[str, dict]:
        if not user_ids:
            return {}
        rows = (await self.session.execute(_FETCH_USER_CONTEXT, {"uids": user_ids})).all()
        return {
            str(r.user_id): {
                "target_job": r.target_job,
                "interest_keywords": r.interest_keywords if isinstance(r.interest_keywords, list) else [],
                "riasec": r.riasec,
                "narrative_summary": r.narrative_summary,
            }
            for r in rows
        }

    async def fetch_context_evidence(self, user_ids: list[str]) -> dict[str, list[dict]]:
        if not user_ids:
            return {}
        rows = (await self.session.execute(_FETCH_CONTEXT_EVIDENCE, {"uids": user_ids})).all()
        out: dict[str, list[dict]] = {}
        for r in rows:
            out.setdefault(str(r.user_id), []).append(
                {"dimension": r.dimension, "polarity": r.polarity, "content": r.content}
            )
        return out

    async def update_sync_explanation(self, user_id: str, sector_slug: str, explanation: str) -> None:
        await self.session.execute(
            _UPDATE_SYNC_EXPLANATION,
            {"user_id": user_id, "sector_slug": sector_slug, "explanation": explanation},
        )

    async def update_match_explanation(self, user_id: str, opportunity_id: int, explanation: str) -> None:
        await self.session.execute(
            _UPDATE_MATCH_EXPLANATION,
            {"user_id": user_id, "opportunity_id": opportunity_id, "explanation": explanation},
        )
```

- [ ] **Step 2: 서비스 작성**

`backend/domain/market_insight/hub/services/recommend_explain_service.py` 생성.

```python
# 추천 설명 서비스 — 설명 없는 Sync/Chance 상위 항목을 사용자당 LLM 1회로 일괄 설명(일일 배치)

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from core.config.settings import get_settings
from core.llm.client import LlmClient
from domain.market_insight.hub.repositories.recommend_explain_repository import (
    RecommendExplainRepository,
)
from domain.market_insight.hub.services.sync_refine_service import INSUFFICIENT_BADGE
from domain.market_insight.hub.services.user_embed_text import RIASEC_LABEL

logger = logging.getLogger(__name__)

TOP_SYNC = 3
TOP_CHANCE = 10
EVIDENCE_POS = 5
EVIDENCE_DISLIKE = 3
MAX_USERS_PER_RUN = 200


def _is_dislike(ev: dict) -> bool:
    return ev.get("dimension") == "dislike" or ev.get("polarity") == "dislike"


def _build_user_context(ctx_row: dict | None, evidence: list[dict]) -> dict:
    """LLM 프롬프트용 사용자 컨텍스트(순수). 비민감 근거만 받는다는 전제(리포 필터)."""
    ctx = ctx_row or {}
    riasec = ctx.get("riasec")
    codes = riasec.get("top_codes") if isinstance(riasec, dict) else None
    labels = [RIASEC_LABEL[c] for c in codes if c in RIASEC_LABEL] if isinstance(codes, list) else []
    positives = [e["content"] for e in evidence if not _is_dislike(e)][:EVIDENCE_POS]
    dislikes = [e["content"] for e in evidence if _is_dislike(e)][:EVIDENCE_DISLIKE]
    return {
        "target_job": ctx.get("target_job"),
        "interest_keywords": ctx.get("interest_keywords") or [],
        "riasec_labels": labels,
        "narrative": ctx.get("narrative_summary"),
        "positives": positives,
        "dislikes": dislikes,
    }


class RecommendExplainService:
    """설명 없는 오늘 Sync 상위·Chance 상위 항목을 사용자 단위로 묶어 LLM 설명 생성·기록."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = RecommendExplainRepository(session)
        settings = get_settings()
        self._api_key = settings.openai_api_key
        self._model = settings.llm_classify_model
        self._explainer = self._default_explainer

    async def _default_explainer(
        self, user_context: dict, sync_items: list[dict], chance_items: list[dict]
    ) -> dict:
        llm = LlmClient(api_key=self._api_key, model=self._model)
        return await llm.explain_recommendations(user_context, sync_items, chance_items)

    async def explain_pending(self, limit: int = MAX_USERS_PER_RUN) -> dict:
        """설명 대상 사용자를 스캔해 사용자당 1회 생성한다. 건별 실패 격리·멱등."""
        if not self._api_key:
            return {"skipped": True, "reason": "no_api_key"}
        sync_rows = await self.repo.fetch_unexplained_sync(TOP_SYNC, INSUFFICIENT_BADGE)
        match_rows = await self.repo.fetch_unexplained_matches(TOP_CHANCE)

        by_user: dict[str, dict] = {}
        for r in sync_rows:
            by_user.setdefault(str(r.user_id), {"sync": [], "chance": []})["sync"].append(
                {
                    "sector_slug": r.sector_slug,
                    "sector_name": r.sector_name,
                    "score": r.score,
                    "badge": r.badge,
                    "affinity_score": float(r.affinity_score) if r.affinity_score is not None else None,
                    "trend_score": float(r.trend_score) if r.trend_score is not None else None,
                }
            )
        for r in match_rows:
            by_user.setdefault(str(r.user_id), {"sync": [], "chance": []})["chance"].append(
                {
                    "opportunity_id": int(r.opportunity_id),
                    "title": r.title,
                    "opportunity_type": r.opportunity_type,
                    "match_score": r.match_score,
                    "match_reason": r.match_reason,
                }
            )

        uids = list(by_user)[:limit]
        ctx_map = await self.repo.fetch_user_context(uids)
        ev_map = await self.repo.fetch_context_evidence(uids)

        processed = failed = written = 0
        for uid in uids:
            items = by_user[uid]
            try:
                user_context = _build_user_context(ctx_map.get(uid), ev_map.get(uid, []))
                result = await self._explainer(user_context, items["sync"], items["chance"])
                for it in result.get("sync", []):
                    await self.repo.update_sync_explanation(uid, it["sector_slug"], it["text"])
                    written += 1
                for it in result.get("chance", []):
                    await self.repo.update_match_explanation(uid, it["opportunity_id"], it["text"])
                    written += 1
                await self.session.commit()
                processed += 1
            except Exception as e:
                await self.session.rollback()
                logger.warning(f"추천 설명 생성 실패(user {uid}): {e}")
                failed += 1
        return {"users": len(uids), "processed": processed, "failed": failed, "written": written}
```

- [ ] **Step 3: 스케줄러 등록**

`backend/core/scheduler.py` — 상단 서비스 import 구역(기존 `SyncRefineService` import 근처)에 추가.

```python
from domain.market_insight.hub.services.recommend_explain_service import RecommendExplainService
```

`_job_sync_refine` 아래에 잡 본문 추가.

```python
async def _job_recommend_explain() -> dict[str, Any]:
    async with AsyncSessionLocal() as session:
        return await RecommendExplainService(session).explain_pending()
```

`_REFINE_PIPELINE` 튜플 마지막(`("sync_refine", _job_sync_refine),` 뒤)에 추가.

```python
    # 설명은 재점수 뒤에 생성해야 무효화(CASE NULL)와 경합하지 않는다.
    ("recommend_explain", _job_recommend_explain),
```

- [ ] **Step 4: 서비스 통합 테스트 작성 (FakeLLM · Neon)**

`backend/scripts/recommend_explain_service_test.py` 생성.

```python
# RecommendExplainService — FakeLLM 설명 기록·멱등·민감 미주입·dislike 전달 (Neon 통합)

from __future__ import annotations

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

from sqlalchemy import text

from core.database import AsyncSessionLocal
from domain.market_insight.hub.services.recommend_explain_service import RecommendExplainService

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


async def _seed_cleanup(s, uid: str, slug: str, opp: int) -> None:
    await s.execute(text(
        "DELETE FROM sync_scores_daily WHERE user_id = CAST(:u AS UUID) "
        "AND sector_slug = :sl AND recorded_date = CURRENT_DATE"), {"u": uid, "sl": slug})
    await s.execute(text(
        "DELETE FROM user_chance_matches WHERE user_id = CAST(:u AS UUID) AND opportunity_id = :o"
    ), {"u": uid, "o": opp})
    await s.execute(text(
        "DELETE FROM user_self_model_evidence WHERE user_id = CAST(:u AS UUID) "
        "AND content IN ('민감한 사정', '야근을 싫어함')"), {"u": uid})
    await s.commit()


async def run() -> int:
    async with AsyncSessionLocal() as s:
        uid = str((await s.execute(text("SELECT id FROM users ORDER BY created_at LIMIT 1"))).scalar_one())
        slug = (await s.execute(text("SELECT slug FROM sectors ORDER BY slug LIMIT 1"))).scalar_one()
        opp = (await s.execute(text(
            "SELECT id FROM chance_opportunities WHERE is_active = true "
            "AND (d_day_date IS NULL OR d_day_date >= CURRENT_DATE) ORDER BY id LIMIT 1"
        ))).scalar_one()
        await _seed_cleanup(s, uid, slug, opp)

        # 시드 — 설명 NULL 인 오늘 Sync 행 + 매치 행, 민감/비민감 근거
        await s.execute(text(
            "INSERT INTO sync_scores_daily (user_id, sector_slug, recorded_date, score, badge) "
            "VALUES (CAST(:u AS UUID), :sl, CURRENT_DATE, 72, '적합')"), {"u": uid, "sl": slug})
        await s.execute(text(
            "INSERT INTO user_chance_matches (user_id, opportunity_id, match_score, match_reason) "
            "VALUES (CAST(:u AS UUID), :o, 80, '의미 유사도 60점') "
            "ON CONFLICT (user_id, opportunity_id) DO UPDATE SET match_score = 80, "
            "match_reason = '의미 유사도 60점', match_explanation = NULL"), {"u": uid, "o": opp})
        for dim, pol, content, sens in [
            ("dislike", "dislike", "야근을 싫어함", False),
            ("sensitive", None, "민감한 사정", True),
        ]:
            await s.execute(text(
                "INSERT INTO user_self_model_evidence "
                "(user_id, dimension, polarity, content, confidence, is_sensitive, content_hash, source) "
                "VALUES (CAST(:u AS UUID), :d, :p, :c, 0.9, :s, md5(:d || COALESCE(:p,'') || :c), 'coach_extraction') "
                "ON CONFLICT (user_id, content_hash) DO NOTHING"
            ), {"u": uid, "d": dim, "p": pol, "c": content, "s": sens})
        await s.commit()

        svc = RecommendExplainService(s)
        svc._api_key = svc._api_key or "test-key"  # 키 부재 환경에서도 FakeLLM 경로 실행
        captured: list[dict] = []

        async def fake_explainer(user_context, sync_items, chance_items):
            captured.append({"ctx": user_context, "sync": sync_items, "chance": chance_items})
            out = {"sync": [], "chance": []}
            for i in sync_items:
                if i["sector_slug"] == slug:
                    out["sync"].append({"sector_slug": slug, "text": "관심과 정렬된 섹터예요."})
            for i in chance_items:
                if i["opportunity_id"] == opp:
                    out["chance"].append({"opportunity_id": opp, "text": "포부와 맞닿은 공고예요."})
            return out

        svc._explainer = fake_explainer
        res = await svc.explain_pending()
        check("처리 성공", res.get("processed", 0) >= 1 and res.get("failed") == 0, str(res))

        v = (await s.execute(text(
            "SELECT explanation FROM sync_scores_daily WHERE user_id = CAST(:u AS UUID) "
            "AND sector_slug = :sl AND recorded_date = CURRENT_DATE"), {"u": uid, "sl": slug})).scalar_one()
        check("sync 설명 기록", v == "관심과 정렬된 섹터예요.", str(v))
        v = (await s.execute(text(
            "SELECT match_explanation FROM user_chance_matches "
            "WHERE user_id = CAST(:u AS UUID) AND opportunity_id = :o"), {"u": uid, "o": opp})).scalar_one()
        check("chance 설명 기록", v == "포부와 맞닿은 공고예요.", str(v))

        # 프롬프트 컨텍스트 — 민감 미주입·dislike 전달
        blob = json.dumps([c["ctx"] for c in captured], ensure_ascii=False)
        check("민감 근거 미주입", "민감한 사정" not in blob, blob[:200])
        my_ctx = [c["ctx"] for c in captured if "야근을 싫어함" in (c["ctx"].get("dislikes") or [])]
        check("dislike 전달", len(my_ctx) >= 1)

        # 멱등 — 시드 사용자 항목이 다시 대상이 되지 않음
        captured.clear()
        await svc.explain_pending()
        again = [
            c for c in captured
            if any(i.get("sector_slug") == slug for i in c["sync"])
            or any(i.get("opportunity_id") == opp for i in c["chance"])
        ]
        check("멱등(재대상 없음)", len(again) == 0, str(len(again)))

        await _seed_cleanup(s, uid, slug, opp)
    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
```

- [ ] **Step 5: 서비스 테스트 실행**

Run: `python scripts/recommend_explain_service_test.py`
Expected: `결과: PASS=6 FAIL=0`, exit 0.

주의 — dev DB 에 다른 사용자의 설명 NULL 행이 있으면 fake explainer 가 그 사용자에 대해서도 호출되지만 빈 결과를 돌려주므로(위 코드) 부작용 없다.

- [ ] **Step 6: 배선 스모크 작성·실행 (LLM 무호출)**

`backend/scripts/recommend_explain_job_test.py` 생성.

```python
# 추천 설명 잡 배선 스모크 — 파이프라인 마지막 스텝 등록·잡 callable (LLM 무호출)

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

from core.scheduler import _REFINE_PIPELINE, _job_recommend_explain

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
    names = [n for n, _ in _REFINE_PIPELINE]
    check("마지막 스텝 recommend_explain", names[-1] == "recommend_explain", str(names))
    check("sync_refine 뒤에 위치", names.index("recommend_explain") > names.index("sync_refine"))
    check("잡 callable", callable(_job_recommend_explain))
    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(run())
```

Run: `python scripts/recommend_explain_job_test.py`
Expected: `결과: PASS=3 FAIL=0`, exit 0.

- [ ] **Step 7: 기존 회귀 실행**

Run: `python scripts/scheduler_refine_pipeline_test.py`
Expected: FAIL=0. (파이프라인 스텝 목록을 단정하는 체크가 있으면 `recommend_explain` 추가를 반영해 그 테스트를 갱신한다.)

- [ ] **Step 8: 커밋**

```bash
git add backend/domain/market_insight/hub/repositories/recommend_explain_repository.py backend/domain/market_insight/hub/services/recommend_explain_service.py backend/core/scheduler.py backend/scripts/recommend_explain_service_test.py backend/scripts/recommend_explain_job_test.py
git commit -m "feat(sp3): 추천 설명 일일 배치(사용자당 LLM 1회)·정제 파이프라인 등록"
```

(`scheduler_refine_pipeline_test.py` 를 갱신했다면 add 목록에 포함한다.)

---

### Task 5: 프론트 설명 노출 (Sync 행·Chance 카드)

**Files:**
- Modify: `www.yeotaeho.kr/src/lib/api/dashboard.ts`
- Modify: `www.yeotaeho.kr/src/components/features/dashboard/DashboardView.tsx`

**Interfaces:**
- Consumes: Task 2 가 노출한 API 필드 — `/api/sync/scores` 항목의 `explanation: string | null`, `/api/chance/matches` 항목의 `match_explanation: string | null`.
- Produces: 없음(말단 UI).

- [ ] **Step 1: `dashboard.ts` 타입·매핑 확장**

`SyncScoreLive` 인터페이스에 필드 추가(`badge` 아래).

```typescript
  explanation: string | null;
```

(`fetchSyncScores` 는 서버 배열을 그대로 반환하므로 매핑 수정 불필요.)

`ChanceMatchLive` 인터페이스에 필드 추가(`match_reason` 아래).

```typescript
  match_explanation: string | null;
```

`fetchMatches` 의 매핑 객체에 라인 추가(`match_reason` 매핑 아래).

```typescript
    match_explanation: (m.match_explanation ?? null) as string | null,
```

- [ ] **Step 2: `DashboardView.tsx` — Sync 행 서브텍스트**

`SyncRow` 타입을 교체.

```typescript
type SyncRow = { trend: string; score: number; badge?: string; explanation?: string };
```

`trendSync` 매핑에 필드 추가.

```typescript
  const trendSync: SyncRow[] = (data ?? []).map((s) => ({
    trend: s.sector_name,
    score: s.score,
    badge: s.badge ?? undefined,
    explanation: s.explanation ?? undefined,
  }));
```

행 렌더의 `<Progress ... />` 바로 아래에 추가.

```tsx
                  {row.explanation && (
                    <p className="mt-2 text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
                      {row.explanation}
                    </p>
                  )}
```

- [ ] **Step 3: `DashboardView.tsx` — Chance 카드 서브텍스트**

`ChanceCard` 타입을 교체(옵셔널이라 제네릭 공고 폴백과 호환).

```typescript
type ChanceCard = {
  id: number;
  title: string;
  opportunity_type: string | null;
  host_name: string | null;
  d_day_date: string | null;
  match_reason?: string | null;
  match_explanation?: string | null;
};
```

카드의 제목 `<p className="mt-3 text-sm font-semibold ...">{item.title}</p>` 바로 아래에 추가.

```tsx
              {(item.match_explanation ?? item.match_reason) && (
                <p className="mt-1.5 text-xs text-slate-500 dark:text-slate-400 leading-relaxed line-clamp-2">
                  {item.match_explanation ?? item.match_reason}
                </p>
              )}
```

- [ ] **Step 4: 타입 검증**

Run: `cd www.yeotaeho.kr; pnpm exec tsc --noEmit`
Expected: 출력 없음(0 에러).

- [ ] **Step 5: 커밋**

```bash
git add www.yeotaeho.kr/src/lib/api/dashboard.ts www.yeotaeho.kr/src/components/features/dashboard/DashboardView.tsx
git commit -m "feat(sp3): Sync 행·Chance 카드에 추천 설명 서브텍스트 노출"
```

---

## 최종 검증 (whole-branch)

- [ ] 백엔드 전체 회귀 — SP-3 신규 6종 + 기존 스위트.

Run (cwd `backend/`, 각각 FAIL=0 확인):

```bash
python scripts/self_model_embed_text_test.py
python scripts/self_model_embed_candidacy_test.py
python scripts/explanation_invalidation_test.py
python scripts/recommend_explain_parse_test.py
python scripts/recommend_explain_service_test.py
python scripts/recommend_explain_job_test.py
python scripts/user_embed_text_test.py
python scripts/user_reembed_test.py
python scripts/chance_user_terms_test.py
python scripts/embed_helpers_test.py
python scripts/sync_score_test.py
python scripts/chance_extract_match_test.py
python scripts/scheduler_refine_pipeline_test.py
python scripts/self_model_merge_test.py
python scripts/self_model_repository_test.py
python scripts/self_model_endpoint_test.py
python scripts/self_model_extraction_test.py
python scripts/coach_service_test.py
```

- [ ] 프론트 — `cd www.yeotaeho.kr; pnpm exec tsc --noEmit` 0 에러.
- [ ] 리뷰 게이트 — code-reviewer 에이전트 whole-branch 리뷰 → Codex `/codex:review --base <시작 ref> --scope branch`.
