# SP-6① Big Five를 추천 설명 레이어에 활용 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** SP-5에서 채점한 Big Five를 추천 설명 레이어에만 녹인다 — `big_five_traits` 순수 함수가 뚜렷한 축만 강점·중립 서술어로 뽑아 "왜 이 추천" LLM 컨텍스트에 넣고, 프롬프트가 공고 적합 시에만 성격을 언급하게 한다. 점수·임베딩·순위 불변.

**Architecture:** 스펙 `backend/docs/superpowers/specs/2026-07-03-big-five-recommend-explain-design.md` 기준. 단일 태스크 — recommend 경로(리포 컨텍스트 쿼리·서비스 특질 파생·프롬프트)만 손댄다. 응집돼 한 커밋·한 리뷰 게이트로 처리.

**Tech Stack:** FastAPI · SQLAlchemy 2.0 async(text SQL) · OpenAI(chat JSON mode).

## Global Constraints

- 한국어 문장 종결은 `.` `?` `!` 만 — `:` 로 끝내지 않는다.
- 커밋은 논리 단위별. `git add .` 금지 — 파일 명시, `.omc/`·`.superpowers/`·`__pycache__` 제외. 커밋 메시지 끝 `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>` 트레일러.
- 백엔드 테스트는 `backend/scripts/*_test.py` 관행(PASS/FAIL check, `python scripts/<name>_test.py`). 통합은 dev Neon — 시드 cleanup.
- 상수 `TRAIT_MARGIN = 12`. 뚜렷한 축 = display 점수가 50±12 밖(높음 ≥62·낮음 ≤38). 중립은 스킵.
- **신경성 N은 정서안정성(100−N) 관점만** — 병리·약점 규정 금지(강점·중립 서술만).
- **점수·임베딩·Sync/Chance 순위 불변** — 이 SP는 설명 레이어만 바꾼다.
- 민감 근거는 프롬프트 컨텍스트에 미주입(기존 리포 필터 유지).

---

### Task 1: Big Five 특질을 추천 설명 컨텍스트에 주입

**Files:**
- Modify: `backend/domain/market_insight/hub/repositories/recommend_explain_repository.py` (`_FETCH_USER_CONTEXT`·`fetch_user_context`)
- Modify: `backend/domain/market_insight/hub/services/recommend_explain_service.py` (`big_five_traits`·`_build_user_context`)
- Modify: `backend/core/llm/client.py` (`_RECOMMEND_EXPLAIN_SYSTEM_PROMPT`)
- Test(신규): `backend/scripts/big_five_traits_test.py` (순수)
- Modify(테스트): `backend/scripts/recommend_explain_service_test.py` (personality_traits 전달·big_five 시드)

**Interfaces:**
- Consumes: 기존 `RecommendExplainRepository.fetch_user_context`·`_build_user_context(ctx_row, evidence)`·`RecommendExplainService`.
- Produces: `recommend_explain_service.big_five_traits(big_five: dict | None) -> list[str]` · 상수 `TRAIT_MARGIN` · `_build_user_context` 반환에 `personality_traits: list[str]` · `fetch_user_context` dict 에 `big_five`.

- [ ] **Step 1: `big_five_traits` 순수 실패 테스트 작성**

`backend/scripts/big_five_traits_test.py` 생성.

```python
# Big Five 점수→강점·중립 서술어(뚜렷한 축만·정서안정성 프레이밍) 순수 테스트

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

from domain.market_insight.hub.services.recommend_explain_service import TRAIT_MARGIN, big_five_traits

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
    check("TRAIT_MARGIN 12", TRAIT_MARGIN == 12)

    # 뚜렷한 축만 — C 높음·E 낮음, 나머지 중립(50)은 스킵
    t = big_five_traits({"scores": {"O": 50, "C": 85, "E": 30, "A": 55, "N": 50}})
    check("C 높음 서술", "체계적이고 성실함" in t, str(t))
    check("E 낮음 서술", "혼자 깊이 집중하는 걸 선호" in t, str(t))
    check("중립 O·A 스킵", all("개방" not in x and "협력" not in x and "독립" not in x for x in t), str(t))
    check("중립 N 스킵(안정성 문구 없음)", all("안정" not in x and "위험을 살핌" not in x for x in t), str(t))

    # 정서안정성 — N 낮음(안정성 높음) → 차분·안정
    t2 = big_five_traits({"scores": {"O": 50, "C": 50, "E": 50, "A": 50, "N": 20}})
    check("N 낮음 → 안정 서술", "차분하고 정서적으로 안정적" in t2, str(t2))
    # N 높음(안정성 낮음) → 신중 서술(병리 아님)
    t3 = big_five_traits({"scores": {"O": 50, "C": 50, "E": 50, "A": 50, "N": 80}})
    check("N 높음 → 신중 서술", "신중하게 위험을 살핌" in t3, str(t3))
    check("N 높음도 병리 단정 없음", all("불안" not in x and "예민함" not in x for x in t3), str(t3))

    # 낮은 쪽 서술어 커버(O·A)
    t4 = big_five_traits({"scores": {"O": 30, "C": 50, "E": 50, "A": 30, "N": 50}})
    check("O 낮음 서술", "익숙함·실용을 선호" in t4, str(t4))
    check("A 낮음 서술", "독립적이고 솔직함" in t4, str(t4))

    # 빈/누락 입력 → 빈 리스트
    check("None 빈 리스트", big_five_traits(None) == [])
    check("scores 없음 빈 리스트", big_five_traits({"raw": {}}) == [])

    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(run())
```

- [ ] **Step 2: 실패 확인**

Run: `python scripts/big_five_traits_test.py` (cwd `backend/`)
Expected: `ImportError: cannot import name 'TRAIT_MARGIN'` 또는 `'big_five_traits'`.

- [ ] **Step 3: `big_five_traits` + `_build_user_context` 구현**

`recommend_explain_service.py` 의 기존 상수 구역(`EVIDENCE_POS` 등 근처)에 추가.

```python
TRAIT_MARGIN = 12  # display 점수가 50±이 값 밖일 때만 뚜렷한 특질로 서술(중립 스킵)

_BIG_FIVE_TRAIT_DESC = {
    "O": ("새로움·아이디어에 개방적", "익숙함·실용을 선호"),
    "C": ("체계적이고 성실함", "유연하고 즉흥적"),
    "E": ("사람과 교류에서 에너지를 얻음", "혼자 깊이 집중하는 걸 선호"),
    "A": ("협력적이고 배려심 있음", "독립적이고 솔직함"),
}
# 신경성 N 은 정서안정성(100-N) 관점으로만 — 병리·약점 규정 금지.
_STABILITY_DESC = ("차분하고 정서적으로 안정적", "신중하게 위험을 살핌")


def big_five_traits(big_five: dict | None) -> list[str]:
    """Big Five 점수에서 뚜렷한 축만 강점·중립 서술어로 변환한다. 순수·결정론.

    각 축 점수가 50±TRAIT_MARGIN 밖일 때만 서술(중립 스킵). N 은 정서안정성(100-N) 관점으로만.
    """
    scores = big_five.get("scores") if isinstance(big_five, dict) else None
    if not isinstance(scores, dict):
        return []
    traits: list[str] = []
    for code in ("O", "C", "E", "A"):
        v = scores.get(code)
        if not isinstance(v, (int, float)) or isinstance(v, bool):
            continue
        if v >= 50 + TRAIT_MARGIN:
            traits.append(_BIG_FIVE_TRAIT_DESC[code][0])
        elif v <= 50 - TRAIT_MARGIN:
            traits.append(_BIG_FIVE_TRAIT_DESC[code][1])
    n = scores.get("N")
    if isinstance(n, (int, float)) and not isinstance(n, bool):
        stability = 100 - n
        if stability >= 50 + TRAIT_MARGIN:
            traits.append(_STABILITY_DESC[0])
        elif stability <= 50 - TRAIT_MARGIN:
            traits.append(_STABILITY_DESC[1])
    return traits
```

`_build_user_context` 반환 dict 에 personality_traits 추가.

```python
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
        "personality_traits": big_five_traits(ctx.get("big_five")),
    }
```

- [ ] **Step 4: 순수 테스트 통과 확인**

Run: `python scripts/big_five_traits_test.py`
Expected: `결과: PASS=12 FAIL=0`, exit 0.

- [ ] **Step 5: 리포 컨텍스트 쿼리에 big_five 추가**

`recommend_explain_repository.py` `_FETCH_USER_CONTEXT` SELECT 목록에 `sm.big_five` 추가.

```python
_FETCH_USER_CONTEXT = text(
    """
    SELECT u.id AS user_id, p.target_job, p.interest_keywords,
           sm.riasec, sm.narrative_summary, sm.big_five
    FROM users u
    LEFT JOIN user_sync_profiles p ON p.user_id = u.id
    LEFT JOIN user_self_model sm ON sm.user_id = u.id
    WHERE u.id IN :uids
    """
).bindparams(bindparam("uids", expanding=True, type_=UUID(as_uuid=False)))
```

`fetch_user_context` 반환 dict 에 `"big_five": r.big_five` 추가.

```python
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
                "big_five": r.big_five,
            }
            for r in rows
        }
```

- [ ] **Step 6: 프롬프트에 personality_traits 지침 추가**

`core/llm/client.py` `_RECOMMEND_EXPLAIN_SYSTEM_PROMPT` 를 다음으로 교체.

```python
_RECOMMEND_EXPLAIN_SYSTEM_PROMPT = (
    "너는 청년 진로 내비게이터의 추천 설명가다. 사용자 컨텍스트(직무·관심·자기모델: 성향 라벨·서사·"
    "성격 특질 personality_traits·좋아하는 것 positives·회피하는 것 dislikes)와 추천 항목별 결정론 지표"
    "(점수·적합도·트렌드·매칭 사유)를 받아, 항목마다 '왜 이 추천인지'를 존댓말 1~2문장으로 쓴다. "
    "입력에 주어진 사실만 사용하고 새 사실을 지어내지 마라. "
    "dislikes 와 명확히 충돌하는 항목은 문장 안에 짧은 주의를 포함하라(점수 언급은 선택). "
    "personality_traits(성격 특질)는 공고·항목이 그 일하는 방식을 분명히 포함할 때만 적합 근거로 언급하고"
    "(불분명하면 성격을 억지로 끌어들이지 마라), 강점·중립 관점으로만 서술하라(약점·병리 규정 금지). "
    "성격 적합은 넓은 섹터보다 개별 공고에 더 자연스럽다. "
    'JSON 객체만 출력하라. 형식: {"sync": [{"sector_slug": <입력에 있던 slug>, "text": <설명>}], '
    '"chance": [{"opportunity_id": <입력에 있던 정수 id>, "text": <설명>}]}. 입력에 없는 slug·id 를 만들지 마라.'
)
```

- [ ] **Step 7: 서비스 통합 테스트 — personality_traits 전달 + big_five 시드**

`recommend_explain_service_test.py` 에서:

(1) 시드 구역(user_self_model 관련 시드 근처, 또는 evidence 시드 앞)에 테스트 사용자의 big_five 를 설정하는 UPSERT 추가. 기존 시드가 `user_self_model` 행을 만들지 않으면 INSERT, 있으면 UPDATE 로 big_five 를 넣는다.

```python
        await s.execute(text(
            "INSERT INTO user_self_model (user_id, big_five, source, updated_at) "
            "VALUES (CAST(:u AS UUID), CAST(:bf AS JSONB), 'consult_extraction', now()) "
            "ON CONFLICT (user_id) DO UPDATE SET big_five = CAST(:bf AS JSONB), updated_at = now()"
        ), {"u": uid, "bf": (
            '{"scores": {"O": 50, "C": 85, "E": 50, "A": 50, "N": 50}, '
            '"raw": {"O": 50, "C": 85, "E": 50, "A": 50, "N": 50}, '
            '"weights": {"O": 5, "C": 5, "E": 5, "A": 5, "N": 5}}'
        )})
        await s.commit()
```

(2) 프롬프트 컨텍스트 단정 구역(민감 미주입·dislike 전달 근처)에 personality_traits 전달 단정 추가.

```python
        my_pt = [c["ctx"] for c in captured if "체계적이고 성실함" in (c["ctx"].get("personality_traits") or [])]
        check("personality_traits 전달", len(my_pt) >= 1, str([c["ctx"].get("personality_traits") for c in captured]))
```

(3) cleanup 이 big_five 를 지우거나 원복하는지 확인 — 기존 `_seed_cleanup` 이 user_self_model 을 지우면 그대로, 아니면 big_five 를 NULL 로 되돌리는 정리 한 줄 추가(테스트 격리).

- [ ] **Step 8: 통합·회귀 실행**

Run: `python scripts/recommend_explain_service_test.py`
Expected: `FAIL=0` (personality_traits 전달 포함).

Run: `python scripts/recommend_explain_parse_test.py; python scripts/recommend_explain_job_test.py`
Expected: 각 FAIL=0.

- [ ] **Step 9: 커밋**

```bash
git add backend/domain/market_insight/hub/repositories/recommend_explain_repository.py backend/domain/market_insight/hub/services/recommend_explain_service.py backend/core/llm/client.py backend/scripts/big_five_traits_test.py backend/scripts/recommend_explain_service_test.py
git commit -m "feat(sp6): Big Five 특질을 추천 설명 컨텍스트에 주입 — 공고 적합 시 성격-적합 서술(점수 불변)"
```

---

## 최종 검증 (whole-branch)

- [ ] 백엔드 회귀 (cwd `backend/`, 각 FAIL=0):
```bash
python scripts/big_five_traits_test.py
python scripts/recommend_explain_service_test.py
python scripts/recommend_explain_parse_test.py
python scripts/recommend_explain_job_test.py
python scripts/big_five_scoring_test.py
python scripts/self_model_extraction_test.py
```
- [ ] 리뷰 게이트 — code-reviewer 에이전트 whole-branch → Codex `/codex:review --base <시작 ref> --scope branch`.
