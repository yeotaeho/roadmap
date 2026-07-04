# SP-9 상담실 자기모델 배경 기억 + 진행 가시화 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ①상담사가 파악한 자기모델을 대화에 배경 기억으로 반영하고, ②인터뷰 커버리지 진행률·완료를 성향 지도 패널에 보여준다.

**Architecture:** 스펙 `backend/docs/superpowers/specs/2026-07-04-consult-self-model-context-progress-design.md`. ① `_load_context_system`이 `self_model_memory()` 블록을 시스템 프롬프트에 append(읽기 전용·신호 게이팅). ② plan 노드가 턴마다 `coverage` SSE 이벤트를 방출 → 프론트가 SelfModelPanel 헤더에 N/11 슬림 바 + 완료 배지. SSE additive.

**Tech Stack:** LangGraph(consult_graph) · FastAPI SSE · OpenAI chat · Next.js/TS/TanStack Query.

## Global Constraints

- 한국어 문장 종결 `.` `?` `!` 만. 커밋 논리 단위, `git add .` 금지(파일 명시). 트레일러 `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- **SSE additive** — 기존 `delta`/`done`/`error`/`self_model_updated` 불변, `coverage` 추가(프론트 구파서 무시).
- **자기모델 읽기 전용·민감 미주입**(`include_sensitive=False`). 배경 기억은 신호 있는 축만(초기 all-50 미주입). market_insight 미import(user_intelligence 도메인 내 직렬화).
- **숨은 배경 기억 톤** — 단정 금지·이미 파악된 축 재질문 금지·더 깊은 질문/개인화에만.
- 백엔드 테스트 `backend/scripts/*_test.py`(cwd `backend/`). 프론트 `pnpm exec tsc --noEmit` 0. **Windows 로컬은 커버리지 리셋** — 라이브 e2e는 Docker/Linux, 로직은 유닛테스트로.

---

### Task 1: ① 자기모델 배경 기억 주입 (백엔드)

**Files:**
- Modify: `backend/domain/user_intelligence/hub/services/consult_service.py` (`self_model_memory`·`_big_five_memory_traits`·`_load_context_system`)
- Modify: `backend/core/llm/client.py` (`_CONSULT_SYSTEM_PROMPT` 한 문장)
- Test(신규): `backend/scripts/self_model_memory_test.py`
- Modify(테스트): `backend/scripts/consult_service_test.py` (배경 기억 주입 확인)

**Interfaces:**
- Produces: `self_model_memory(model: dict | None) -> str`(신호 있는 축만·없으면 "") · `_load_context_system`이 배경 기억 블록 append.

- [ ] **Step 1: 순수 직렬화 실패 테스트**

`backend/scripts/self_model_memory_test.py` 생성.

```python
# 자기모델 배경 기억 직렬화 순수 테스트 — 신호 게이팅·정서안정성·빈 모델→빈 문자열.

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

from domain.user_intelligence.hub.services.consult_service import self_model_memory

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
    # 신호 있는 모델 — 흥미·성격·서사
    m = {
        "riasec": {"top_codes": ["I", "A"]},
        "bigFive": {"scores": {"O": 80, "C": 75, "E": 45, "A": 50, "N": 20}},
        "narrativeSummary": "탐구를 좋아하는 빌더",
    }
    s = self_model_memory(m)
    check("흥미 라벨", "탐구" in s and "예술" in s, s)
    check("성격 뚜렷 축(개방·성실)", "개방" in s or "새로움" in s, s)
    check("정서안정성(N 낮음→안정)", "안정" in s, s)
    check("중립 축 A 미포함(50)", "배려" not in s and "솔직" not in s, s)
    check("서사 포함", "탐구를 좋아하는 빌더" in s, s)
    check("배경 기억 헤더·단정금지", "배경 기억" in s, s)

    # 신호 없는 모델 → 빈 문자열
    empty = {"riasec": {"top_codes": []}, "bigFive": {"scores": {k: 50 for k in "OCEAN"}}, "narrativeSummary": None}
    check("무신호 → 빈 문자열", self_model_memory(empty) == "", repr(self_model_memory(empty)))
    check("None → 빈 문자열", self_model_memory(None) == "")
    # N 높음 → 신중(병리 아님)
    hi_n = {"riasec": {"top_codes": []}, "bigFive": {"scores": {"O": 50, "C": 50, "E": 50, "A": 50, "N": 85}}, "narrativeSummary": None}
    sn = self_model_memory(hi_n)
    check("N 높음 → 신중 서술", "신중" in sn, sn)
    check("N 높음 병리 없음", "불안" not in sn and "예민" not in sn, sn)

    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(run())
```

- [ ] **Step 2: 실패 확인**

Run: `python scripts/self_model_memory_test.py` (cwd `backend/`)
Expected: `ImportError: cannot import name 'self_model_memory'`.

- [ ] **Step 3: 직렬화 구현**

`consult_service.py`의 `build_consult_context` 근처(모듈 함수 구역)에 추가.

```python
_RIASEC_SHORT = {"R": "현실", "I": "탐구", "A": "예술", "S": "사회", "E": "진취", "C": "관습"}
# Big Five 뚜렷한 축을 강점·중립 서술어로(신경성은 정서안정성 관점·병리 금지). market_insight 미import.
_BF_MEMORY_DESC = {
    "O": ("새로움에 열린", "익숙함을 선호하는"),
    "C": ("체계적이고 성실한", "유연하고 즉흥적인"),
    "E": ("사람들과 어울릴 때 힘이 나는", "혼자 집중하는 걸 편해하는"),
    "A": ("협력적이고 배려하는", "독립적이고 솔직한"),
}
_STABILITY_MEMORY = ("차분하고 안정적인", "신중하게 살피는")
_BF_MEMORY_MARGIN = 12


def _big_five_memory_traits(scores: dict) -> list[str]:
    """Big Five 점수에서 뚜렷한 축만 서술어로. N 은 정서안정성(100-N) 관점."""
    out: list[str] = []
    for code in ("O", "C", "E", "A"):
        v = scores.get(code)
        if not isinstance(v, (int, float)) or isinstance(v, bool):
            continue
        if v >= 50 + _BF_MEMORY_MARGIN:
            out.append(_BF_MEMORY_DESC[code][0])
        elif v <= 50 - _BF_MEMORY_MARGIN:
            out.append(_BF_MEMORY_DESC[code][1])
    n = scores.get("N")
    if isinstance(n, (int, float)) and not isinstance(n, bool):
        stability = 100 - n
        if stability >= 50 + _BF_MEMORY_MARGIN:
            out.append(_STABILITY_MEMORY[0])
        elif stability <= 50 - _BF_MEMORY_MARGIN:
            out.append(_STABILITY_MEMORY[1])
    return out


def self_model_memory(model: dict | None) -> str:
    """비민감 자기모델 → 상담사 배경 기억 문자열. 신호 있는 축만. 없으면 빈 문자열(초기 노이즈 방지)."""
    if not isinstance(model, dict):
        return ""
    parts: list[str] = []
    riasec = model.get("riasec")
    codes = riasec.get("top_codes") if isinstance(riasec, dict) else None
    labels = [_RIASEC_SHORT[c] for c in codes if c in _RIASEC_SHORT] if isinstance(codes, list) else []
    if labels:
        parts.append("- 흥미 성향: " + "·".join(labels))
    big_five = model.get("bigFive")
    scores = big_five.get("scores") if isinstance(big_five, dict) else None
    traits = _big_five_memory_traits(scores) if isinstance(scores, dict) else []
    if traits:
        parts.append("- 성격: " + ", ".join(traits))
    narr = model.get("narrativeSummary")
    if isinstance(narr, str) and narr.strip():
        parts.append("- 한 줄: " + narr.strip())
    if not parts:
        return ""
    return "\n\n[지금까지 파악한 당신 — 잠정적 배경 기억, 단정 금지]\n" + "\n".join(parts)
```

- [ ] **Step 4: 순수 테스트 통과**

Run: `python scripts/self_model_memory_test.py`
Expected: `결과: PASS=10 FAIL=0`.

- [ ] **Step 5: `_load_context_system` 주입 + 프롬프트 지침**

`consult_service.py` 상단 import 에 추가: `from domain.user_intelligence.hub.services.self_model_service import SelfModelService`.

`_load_context_system` 을 교체(기존 본문 뒤에 배경 기억 append).

```python
    async def _load_context_system(self, user_id: str) -> str:
        """상담 시스템 프롬프트 + 사용자 맥락 + 자기모델 배경 기억. 로드 실패는 조용히 생략(진행)."""
        try:
            async with AsyncSessionLocal() as db:
                ctx = await ConsultContextRepository(db).fetch_context(user_id)
            context_str = build_consult_context(ctx)
        except Exception as e:
            logger.warning(f"상담 맥락 로드 실패(맥락 없이 진행): {e}")
            context_str = ""
        memory_str = ""
        try:
            async with AsyncSessionLocal() as db:
                model = await SelfModelService(db).get_self_model(user_id, include_sensitive=False)
            memory_str = self_model_memory(model)
        except Exception as e:  # 자기모델 로드 실패 시 배경 기억 없이 진행한다.
            logger.warning(f"자기모델 배경 기억 로드 실패(생략): {e}")
        return _CONSULT_SYSTEM_PROMPT + ("\n\n" + context_str if context_str else "") + memory_str
```

`core/llm/client.py` `_CONSULT_SYSTEM_PROMPT` 끝 문장(`답변은 따뜻하고 간결하게(보통 3~6문장).`) 앞에 한 문장 삽입.

```python
    "제공될 수 있는 '지금까지 파악한 당신'은 잠정적 배경 기억이다. 사용자에게 단정해 말하지 말고(발견 과정 유지), "
    "이미 파악된 축은 다시 캐묻지 말며, 더 깊은 질문·개인화에만 활용하라. "
```

- [ ] **Step 6: 서비스 테스트 — 배경 기억 주입 확인**

`consult_service_test.py`에서 `_load_context_system`을 직접 호출하는 케이스를 추가하거나(기존 시드 사용자에 자기모델이 있으면), 최소 `self_model_memory`가 시스템 프롬프트 조립에 반영되는지 확인. 기존 스위트가 `_load_context_system`을 그래프로 간접 호출하므로, **자기모델 시드 없이도 회귀가 깨지지 않아야 한다**(무신호 → 빈 문자열 → 기존과 동일). 다음 회귀만 확인하면 충분하다.

Run: `python scripts/consult_service_test.py`
Expected: `FAIL=0`(무신호 사용자는 배경 기억 미주입이라 기존 단정 불변).

- [ ] **Step 7: 커밋**

```bash
git add backend/domain/user_intelligence/hub/services/consult_service.py backend/core/llm/client.py backend/scripts/self_model_memory_test.py
git commit -m "feat(sp9): 자기모델 배경 기억을 상담 프롬프트에 주입 — 숨은 배경 기억 톤·신호 게이팅"
```
(consult_service_test 를 수정했으면 함께 스테이징.)

---

### Task 2: ② 커버리지 SSE 이벤트 (백엔드)

**Files:**
- Modify: `backend/domain/user_intelligence/spokes/infra/consult_graph.py` (plan 노드 coverage writer)
- Modify(테스트): `backend/scripts/consult_graph_test.py` (coverage 이벤트 단정)

**Interfaces:**
- Consumes: 기존 plan 노드·`ALL_AXES`.
- Produces: 매 턴 SSE `{"type":"coverage","covered":N,"total":11}`(프론트 Task 3 소비).

- [ ] **Step 1: 그래프 테스트에 coverage 단정 추가 (실패 확인)**

`consult_graph_test.py`의 기존 svc4 케이스(planner가 `newly_covered:["R","I"]`, focus "A")를 재사용한다. 현재 그 블록은 `await collect(graph4, {...}, cfg4)`의 반환을 버리고 state만 검사하므로, **반환을 변수로 받아** coverage 이벤트를 필터·단정한다. svc4 블록의 collect 줄을 다음처럼 바꾸고(변수 저장) 아래 2줄을 그 케이스 단정들 옆에 추가.

```python
    chunks4 = await collect(graph4, {"user_id": "u1", "session_id": "s4", "message": "네"}, cfg4)
    cov4 = [c for c in chunks4 if c.get("type") == "coverage"]
    check("coverage 이벤트 방출", len(cov4) >= 1, str(cov4))
    check("coverage covered=2 total=11", bool(cov4) and cov4[-1].get("covered") == 2 and cov4[-1].get("total") == 11, str(cov4))
```
(기존 svc4 단정 `plan 커버리지 병합`·`인터뷰 지침 주입`은 그대로 유지 — collect를 변수로 받는 변경만.)

- [ ] **Step 2: 실패 확인**

Run: `python scripts/consult_graph_test.py`
Expected: coverage 단정 FAIL(plan 노드가 아직 이벤트 미방출).

- [ ] **Step 3: plan 노드에 coverage writer 추가**

`consult_graph.py` `plan` 노드의 `return {"coverage": coverage, ...}`(현재 line 110) **직전**에 삽입.

```python
        get_stream_writer()({
            "type": "coverage",
            "covered": sum(1 for a in ALL_AXES if coverage.get(a)),
            "total": len(ALL_AXES),
        })
        return {"coverage": coverage, "mode": mode, "plan": {"focus_axis": focus, "focus_hint": hint}}
```
(`get_stream_writer`는 이미 import됨. 비스트리밍 컨텍스트에선 no-op writer 라 안전.)

- [ ] **Step 4: 전체 확인**

Run: `python scripts/consult_graph_test.py`
Expected: `결과: PASS=24 FAIL=0`(기존 22 + coverage 2).

Run: `python scripts/consult_service_test.py; python scripts/consult_stream_test.py`
Expected: 각 FAIL=0(coverage 는 additive라 기존 delta/done 단정 불변).

- [ ] **Step 5: 커밋**

```bash
git add backend/domain/user_intelligence/spokes/infra/consult_graph.py backend/scripts/consult_graph_test.py
git commit -m "feat(sp9): plan 노드가 커버리지 SSE 이벤트 방출 — 인터뷰 진행률 소스"
```

---

### Task 3: ② 진행률 바 + 완료 배지 (프론트)

**Files:**
- Modify: `www.yeotaeho.kr/src/lib/api/consult.ts` (`streamConsult` onCoverage)
- Modify: `www.yeotaeho.kr/src/components/features/consult/ConsultView.tsx` (coverage 상태·전달)
- Modify: `www.yeotaeho.kr/src/components/features/consult/SelfModelPanel.tsx` (coverage prop·헤더 바·배지)

**Interfaces:**
- Consumes: Task 2 SSE `{"type":"coverage","covered","total"}`.
- Produces: 없음(말단).

- [ ] **Step 1: consult.ts — onCoverage 콜백**

`streamConsult` 시그니처 마지막에 선택 콜백 추가(기존 호출부 하위호환).

```typescript
export async function streamConsult(
  sessionId: string,
  message: string,
  onDelta: (text: string) => void,
  signal?: AbortSignal,
  onSelfModelUpdated?: () => void,
  onCoverage?: (covered: number, total: number) => void,
): Promise<void> {
```
파서 분기(`self_model_updated` 라인 아래)에 추가. `obj` 타입에 `covered?`, `total?`도 반영.

```typescript
        if (obj.type === 'coverage' && typeof obj.covered === 'number' && typeof obj.total === 'number') {
          onCoverage?.(obj.covered, obj.total);
        }
```
(파서의 `JSON.parse(raw) as {...}` 타입에 `covered?: number; total?: number` 추가.)

- [ ] **Step 2: ConsultView — coverage 상태·SelfModelPanel 전달**

`ConsultView.tsx`:
- 상태 추가: `const [coverage, setCoverage] = useState<{ covered: number; total: number } | null>(null);`
- `streamConsult(...)` 호출을 6인자로 — 기존 5번째 `onSelfModelUpdated` 뒤에 `(covered, total) => setCoverage({ covered, total })` 추가.
- `<SelfModelPanel />` **두 곳**(데스크톱 aside line 291·모바일 drawer line 341)에 `coverage={coverage}` 전달.

- [ ] **Step 3: SelfModelPanel — coverage prop·헤더 바·완료 배지**

`SelfModelPanel.tsx`:
- 시그니처: `export function SelfModelPanel({ coverage }: { coverage?: { covered: number; total: number } | null }) {`
- 헤더("나의 성향 지도" 타이틀 행 아래)에 슬림 바 렌더. 완료(covered===total && total>0)면 배지.

```tsx
      {coverage && coverage.total > 0 && (
        <div className="mt-2">
          {coverage.covered >= coverage.total ? (
            <span className="inline-flex items-center gap-1 rounded-full bg-indigo-50 px-2 py-0.5 text-[11px] font-semibold text-indigo-600 dark:bg-indigo-500/15 dark:text-indigo-300">
              <Sparkles className="h-3 w-3" /> 성향이 정리됐어요
            </span>
          ) : (
            <>
              <div className="mb-1 flex items-center justify-between text-[11px] text-slate-500 dark:text-slate-400">
                <span>성향 파악</span>
                <span>{coverage.covered}/{coverage.total}</span>
              </div>
              <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-100 dark:bg-slate-700">
                <div
                  className="h-full rounded-full bg-indigo-500 transition-all"
                  style={{ width: `${Math.round((coverage.covered / coverage.total) * 100)}%` }}
                />
              </div>
            </>
          )}
        </div>
      )}
```
(`Sparkles`는 이미 import됨. 삽입 위치는 헤더 타이틀 행 바로 아래 — 기존 레이아웃 톤 유지.)

- [ ] **Step 4: 타입 검증**

Run: `cd www.yeotaeho.kr; pnpm exec tsc --noEmit`
Expected: 출력 없음(0 에러).

- [ ] **Step 5: 커밋**

```bash
git add www.yeotaeho.kr/src/lib/api/consult.ts www.yeotaeho.kr/src/components/features/consult/ConsultView.tsx www.yeotaeho.kr/src/components/features/consult/SelfModelPanel.tsx
git commit -m "feat(sp9): 성향 지도 헤더에 인터뷰 진행률 바 + 완료 배지 — coverage SSE 연동"
```

---

## 최종 검증 (whole-branch)

- [ ] 백엔드 (cwd `backend/`, 각 FAIL=0): `self_model_memory_test` · `consult_graph_test` · `consult_service_test` · `consult_stream_test` · `interview_bank_test` · `self_model_extraction_test`.
- [ ] 프론트 `pnpm exec tsc --noEmit` 0.
- [ ] 리뷰 게이트 — code-reviewer whole-branch → Codex `--base <시작 ref> --scope branch`.
