# SP-8b 하이브리드 능동 인터뷰 + 라운드 완료 즉시 추출 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 상담실이 설문 근거로 **먼저 묻는** 하이브리드 인터뷰가 되게 한다 — 11축 커버리지를 추적하며 미커버 축을 자연스럽게 질문(고민이 나오면 경청 전환), 전 축 커버 시 **즉시 자기모델 추출** + SSE `self_model_updated`로 성향 지도 실시간 갱신, 실행 가이드는 코치로 위임.

**Architecture:** 스펙 `backend/docs/superpowers/specs/2026-07-04-consult-redesign-langgraph-interview-design.md` §B·§C. SP-8a 그래프에 **plan 노드**(작은 JSON LLM 호출 — 모드·신규 커버 축·다음 질문 축/각도 판단)와 **extract 노드**(전 축 커버 시 1회 즉시 추출)를 추가한다: `prepare → plan → respond → persist → extract`. 커버리지·모드·round_done은 LangGraph state(체크포인터로 내구화, 무체크포인터 환경은 일일 배치 백스톱). plan·extract는 서비스 심(`_planner`·`_extract_round`)으로 주입 가능(기존 `_streamer` 패턴).

**Tech Stack:** langgraph 1.1.10 · OpenAI JSON mode · FastAPI SSE · Next.js/TanStack Query.

## Global Constraints

- 한국어 문장 종결 `.` `?` `!` 만. 새 소스 파일 첫 줄 한 줄 한국어 역할 주석.
- 커밋 논리 단위, `git add .` 금지(파일 명시). 커밋 트레일러 `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- **축 코드 네임스페이스** — RIASEC `R I A S E C` · Big Five `BF_O BF_C BF_E BF_A BF_N`(RIASEC E·C와 충돌 방지). 총 11축 = `ALL_AXES`.
- **민감정보 원칙** — 민감 주제(트라우마·건강·가족사·경제 사정 등)는 캐묻지 않는다. 흥미·일하는 방식은 능동적으로 물어도 된다.
- **실행 가이드 금지** — 강의·블로그·자격증 등 구체 행동 조언은 코치 위임 안내로 대체.
- **즉시 추출은 비치명** — 실패해도 대화 지속(일일 배치가 수거). 추출 성공 시에만 `self_model_updated` 방출.
- SSE 계약은 additive — 기존 `delta`/`done`/`error` 불변, `self_model_updated` 추가(프론트 구파서는 무시).
- 백엔드 테스트 `backend/scripts/*_test.py`(PASS/FAIL check, cwd `backend/`). 프론트 `pnpm exec tsc --noEmit` 0.

---

### Task 1: 문항 은행 + 인터뷰 플래너 LLM + 프롬프트 개정 + force 추출

**Files:**
- Create: `backend/domain/user_intelligence/hub/services/consult_interview_bank.py`
- Modify: `backend/core/llm/client.py` (`_CONSULT_SYSTEM_PROMPT` 개정 · `_INTERVIEW_PLAN_SYSTEM_PROMPT`·`_INTERVIEW_AXIS_CODES`·`_parse_interview_plan`·`plan_interview` 추가)
- Modify: `backend/domain/user_intelligence/hub/services/self_model_extraction_service.py` (`extract_session` force 파라미터)
- Test(신규): `backend/scripts/interview_bank_test.py`
- Modify(테스트): `backend/scripts/self_model_extraction_test.py` (force 케이스)

**Interfaces:**
- Produces: `INTERVIEW_AXES: dict[str, dict]`(11축, `{"label", "probes"}`) · `ALL_AXES: tuple[str, ...]` · `first_uncovered(coverage: dict) -> str | None` · `axis_label(code) -> str` · `probe_hint(code) -> str | None` · `LlmClient.plan_interview(coverage: dict, recent: list[dict], message: str) -> dict`(반환 `{"mode": "interview"|"listening", "newly_covered": [코드], "focus_axis": 코드|None, "focus_hint": str|None}`) · `extract_session(user_id, session_id, force: bool = False)`.

- [ ] **Step 1: 문항 은행·파서 실패 테스트 작성**

`backend/scripts/interview_bank_test.py` 생성.

```python
# 인터뷰 문항 은행·플랜 파서 순수 테스트 — 11축 구조·헬퍼·JSON 파싱 안전 기본값.

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

from core.llm.client import _parse_interview_plan
from domain.user_intelligence.hub.services.consult_interview_bank import (
    ALL_AXES,
    INTERVIEW_AXES,
    axis_label,
    first_uncovered,
    probe_hint,
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
    check("11축", len(ALL_AXES) == 11 and set(ALL_AXES) == set(INTERVIEW_AXES), str(ALL_AXES))
    check("RIASEC 6 + BF 5",
          all(c in ALL_AXES for c in ("R", "I", "A", "S", "E", "C", "BF_O", "BF_C", "BF_E", "BF_A", "BF_N")))
    check("각 축 label·probes", all(a.get("label") and a.get("probes") for a in INTERVIEW_AXES.values()))
    check("first_uncovered 빈 커버리지", first_uncovered({}) == next(iter(INTERVIEW_AXES)))
    partial = {c: True for c in ALL_AXES if c != "BF_N"}
    check("first_uncovered 부분", first_uncovered(partial) == "BF_N")
    check("first_uncovered 전체 커버", first_uncovered({c: True for c in ALL_AXES}) is None)
    check("axis_label", "탐구" in axis_label("I"))
    check("probe_hint 존재", isinstance(probe_hint("R"), str) and len(probe_hint("R")) > 0)
    check("probe_hint 미지 코드 None", probe_hint("ZZ") is None)

    # 파서 — 정상
    p = _parse_interview_plan('{"mode": "listening", "newly_covered": ["R", "BF_O", "ZZ"], '
                              '"focus_axis": "I", "focus_hint": " 원리 파기 "}')
    check("파서 mode", p["mode"] == "listening")
    check("파서 코드 필터", p["newly_covered"] == ["R", "BF_O"], str(p["newly_covered"]))
    check("파서 focus", p["focus_axis"] == "I" and p["focus_hint"] == "원리 파기", str(p))
    # 파서 — 불량 입력 안전 기본값
    bad = _parse_interview_plan("망가진 json")
    check("파서 불량 기본값", bad == {"mode": "interview", "newly_covered": [], "focus_axis": None, "focus_hint": None}, str(bad))
    check("파서 미지 mode 기본", _parse_interview_plan('{"mode": "chaos"}')["mode"] == "interview")
    check("파서 미지 focus 제외", _parse_interview_plan('{"focus_axis": "ZZ"}')["focus_axis"] is None)

    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(run())
```

- [ ] **Step 2: 실패 확인**

Run: `python scripts/interview_bank_test.py` (cwd `backend/`)
Expected: `ModuleNotFoundError`(consult_interview_bank) 또는 `ImportError`(_parse_interview_plan).

- [ ] **Step 3: 문항 은행 구현**

`backend/domain/user_intelligence/hub/services/consult_interview_bank.py` 생성.

```python
# 상담 인터뷰 문항 은행 — RIASEC 6축·Big Five 5축의 대화형 질문 각도(정식 검사 문항 풀 근거).

from __future__ import annotations

# 실제 검사(워크넷 직업선호도·O*NET Interest Profiler)가 축별 독립 문항 풀을 쓰는 것을 근거로,
# 각 축을 자연스러운 대화 질문 각도(probe)로 변환한다. LLM 은 probe 를 그대로 읽지 않고 참고 각도로 쓴다.
INTERVIEW_AXES: dict[str, dict] = {
    "R": {
        "label": "현실형(손·도구·몸)",
        "probes": [
            "손으로 만들거나 고치거나 몸을 쓰는 활동을 즐기는지, 최근 그런 경험이 있었는지",
            "기계·도구·장비를 다루는 일에 흥미를 느끼는지",
        ],
    },
    "I": {
        "label": "탐구형(원리·분석)",
        "probes": [
            "어떤 주제를 원리까지 파고들었던 경험이 있는지, 무엇이 그렇게 만들었는지",
            "문제를 분석하거나 실험해 보는 활동을 즐기는지",
        ],
    },
    "A": {
        "label": "예술형(창작·표현)",
        "probes": [
            "무언가를 만들거나 표현하는 활동(글·그림·영상·스타일링 등)에 끌리는지",
            "정해진 틀보다 자유로운 방식이 좋은 순간이 언제인지",
        ],
    },
    "S": {
        "label": "사회형(돕기·소통)",
        "probes": [
            "다른 사람을 돕거나 가르쳐 준 경험에서 어떤 기분을 느꼈는지",
            "사람들과 소통하며 무언가를 함께 할 때와 혼자 할 때 중 무엇이 좋은지",
        ],
    },
    "E": {
        "label": "진취형(설득·주도)",
        "probes": [
            "모임이나 프로젝트에서 방향을 정하고 이끌어 본 경험이 있는지",
            "누군가를 설득하거나 목표를 밀어붙이는 상황을 즐기는지",
        ],
    },
    "C": {
        "label": "관습형(정리·체계)",
        "probes": [
            "일정·자료·물건을 정리하고 체계를 잡는 걸 좋아하는지",
            "꼼꼼하게 규칙대로 처리해야 하는 일이 편한지 답답한지",
        ],
    },
    "BF_O": {
        "label": "개방성(새로움·호기심)",
        "probes": [
            "새로운 것(장소·음식·분야)을 시도하는 편인지, 익숙한 게 좋은지",
            "요즘 호기심이 생긴 낯선 주제가 있는지",
        ],
    },
    "BF_C": {
        "label": "성실성(계획·꾸준함)",
        "probes": [
            "일을 계획 세워 진행하는 편인지, 닥쳐서 몰아치는 편인지",
            "꾸준히 이어 온 습관이나 루틴이 있는지",
        ],
    },
    "BF_E": {
        "label": "외향성(에너지 방향)",
        "probes": [
            "사람들과 어울린 뒤 충전되는지, 혼자 있는 시간이 필요해지는지",
            "여럿이 하는 활동과 혼자 몰입하는 활동 중 무엇이 더 자연스러운지",
        ],
    },
    "BF_A": {
        "label": "우호성(협력·배려)",
        "probes": [
            "의견이 부딪힐 때 맞춰 주는 편인지, 자기 생각을 밀고 나가는 편인지",
            "팀에서 갈등이 생기면 주로 어떤 역할을 하는지",
        ],
    },
    "BF_N": {
        "label": "정서반응(스트레스 대처)",
        "probes": [
            "스트레스를 받으면 주로 어떻게 풀고, 회복이 빠른 편인지",
            "중요한 일 전에 긴장을 많이 하는 편인지 담담한 편인지",
        ],
    },
}

ALL_AXES: tuple[str, ...] = tuple(INTERVIEW_AXES)


def first_uncovered(coverage: dict) -> str | None:
    """커버리지에서 아직 신호가 없는 첫 축 코드. 전부 커버면 None."""
    for code in INTERVIEW_AXES:
        if not coverage.get(code):
            return code
    return None


def axis_label(code: str) -> str:
    ax = INTERVIEW_AXES.get(code)
    return ax["label"] if ax else code


def probe_hint(code: str) -> str | None:
    ax = INTERVIEW_AXES.get(code)
    return ax["probes"][0] if ax and ax.get("probes") else None
```

- [ ] **Step 4: LlmClient — 플래너·프롬프트 개정**

`backend/core/llm/client.py`:

(1) `_CONSULT_SYSTEM_PROMPT`(121-126행)를 다음으로 교체.

```python
_CONSULT_SYSTEM_PROMPT = (
    "너는 청년 진로 내비게이터의 'AI 상담사'다. 대화를 통해 사용자의 성격·성향·가치관·호불호를 파악하고, "
    "사용자가 미처 몰랐던 강점·관심 패턴을 짚어 준다. 진로의 방향을 함께 발견하는 것이 목표다. "
    "실행 조언은 하지 않는다 — 강의 수강·블로그 운영·자격증 취득 같은 구체적 행동 가이드와 로드맵·퀘스트 설계는 "
    "모두 코치의 몫이며, 사용자가 원하면 '그 부분은 로드맵 코치가 도와드릴 거예요' 정도로만 위임을 안내한다. "
    "흥미·일하는 방식·좋아하고 싫어하는 것은 대화 흐름 속에서 네가 먼저 자연스럽게 물어도 된다. "
    "다만 민감한 주제(트라우마·건강·가족사·경제 사정 등)는 캐묻지 않고, 사용자가 스스로 꺼낸 경우에만 다룬다. "
    "막연한 응원 대신 통찰을 주는 질문을 던지고, 근거 없는 단정·과장은 피하며, 사용자의 말에서 관찰된 것만 언급한다. "
    "답변은 따뜻하고 간결하게(보통 3~6문장)."
)
```

(2) `_CONSULT_SYSTEM_PROMPT` 아래에 플래너 프롬프트·코드 상수 추가.

```python
_INTERVIEW_AXIS_CODES = ("R", "I", "A", "S", "E", "C", "BF_O", "BF_C", "BF_E", "BF_A", "BF_N")

_INTERVIEW_PLAN_SYSTEM_PROMPT = (
    "너는 진로 상담 대화의 인터뷰 플래너다. 상담사가 사용자의 직업 흥미(RIASEC: R 현실형, I 탐구형, "
    "A 예술형, S 사회형, E 진취형, C 관습형)와 성격(Big Five: BF_O 개방성, BF_C 성실성, BF_E 외향성, "
    "BF_A 우호성, BF_N 정서반응)을 파악하도록 이번 턴을 계획한다. "
    "입력은 축별 커버리지(이미 신호를 확보한 축)·최근 대화·현재 사용자 메시지다. 판단할 것: "
    "(1) mode — 사용자가 고민·감정·힘든 이야기를 꺼내 경청이 먼저면 'listening', 아니면 'interview'. "
    "(2) newly_covered — 현재 사용자 메시지에 어떤 축의 성향 신호가 분명히 담겨 있으면 그 축 코드 목록(확실한 것만, 없으면 빈 배열). "
    "(3) focus_axis — 다음으로 물어볼 미커버 축 1개(mode 가 listening 이면 null). "
    "(4) focus_hint — 그 축을 대화 흐름에 맞게 자연스럽게 묻는 질문 각도 한 문장(한국어, focus_axis 없으면 null). "
    'JSON 만 출력: {"mode": "interview"|"listening", "newly_covered": ["축코드"], '
    '"focus_axis": "축코드"|null, "focus_hint": "문자열"|null}'
)
```

(3) 파서(모듈 레벨, 다른 `_parse_*` 근처)와 메서드(`LlmClient` 내부, `summarize_conversation` 근처) 추가.

```python
def _parse_interview_plan(content: str | None) -> dict:
    """인터뷰 플랜 JSON 파싱 — 코드 검증·안전 기본값(실패 시 interview·빈 커버)."""
    out: dict = {"mode": "interview", "newly_covered": [], "focus_axis": None, "focus_hint": None}
    try:
        data = json.loads(content or "{}")
    except (TypeError, ValueError):
        return out
    if not isinstance(data, dict):
        return out
    if data.get("mode") in ("interview", "listening"):
        out["mode"] = data["mode"]
    nc = data.get("newly_covered")
    if isinstance(nc, list):
        out["newly_covered"] = [c for c in nc if c in _INTERVIEW_AXIS_CODES]
    if data.get("focus_axis") in _INTERVIEW_AXIS_CODES:
        out["focus_axis"] = data["focus_axis"]
    fh = data.get("focus_hint")
    if isinstance(fh, str) and fh.strip():
        out["focus_hint"] = fh.strip()[:200]
    return out
```

```python
    async def plan_interview(self, coverage: dict, recent: list[dict], message: str) -> dict:
        """인터뷰 턴 계획 — 모드·신규 커버 축·다음 질문 축과 각도. 예외는 호출부 폴백."""
        covered = [c for c in _INTERVIEW_AXIS_CODES if (coverage or {}).get(c)]
        uncovered = [c for c in _INTERVIEW_AXIS_CODES if c not in covered]
        convo = "\n".join(f"{m.get('role')}: {m.get('content')}" for m in (recent or [])[-6:])
        user = (
            f"[커버된 축] {', '.join(covered) or '없음'}\n"
            f"[미커버 축] {', '.join(uncovered) or '없음'}\n"
            f"[최근 대화]\n{convo or '(없음)'}\n\n[현재 사용자 메시지]\n{message}"
        )
        resp = await self._client.chat.completions.create(
            model=self._model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _INTERVIEW_PLAN_SYSTEM_PROMPT},
                {"role": "user", "content": user},
            ],
        )
        return _parse_interview_plan(resp.choices[0].message.content)
```

- [ ] **Step 5: extract_session force**

`self_model_extraction_service.py`의 `extract_session` 시그니처·게이트를 교체.

```python
    async def extract_session(self, user_id: str, session_id: str, force: bool = False) -> dict:
        """세션의 미추출 대화에서 자기모델을 갱신한다. 신규 부족 시 스킵(force 는 임계 우회)."""
        sess = await self.coach_repo.get_session(session_id)
        if sess is None:
            return {"skipped": True, "reason": "no_session"}
        extracted_until = sess["extracted_until"]
        msgs = await self.coach_repo.fetch_messages(session_id)
        cutoff = len(msgs)
        new_msgs = msgs[extracted_until:cutoff]
        if not new_msgs:
            return {"skipped": True, "reason": "no_new"}
        if not force and len(new_msgs) < MIN_NEW:
            return {"skipped": True, "reason": "insufficient"}
```
(이후 본문 무변경. `if not new_msgs` 분기가 새로 분리됨 — force 여도 새 메시지 0이면 스킵.)

- [ ] **Step 6: 통과 확인 + force 회귀 케이스**

Run: `python scripts/interview_bank_test.py`
Expected: `결과: PASS=15 FAIL=0`.

`backend/scripts/self_model_extraction_test.py`에 force 케이스 추가 — 기존 테스트의 `svc._extractor` 주입·시드 패턴을 재사용해, **MIN_NEW 미만(예: 2개) 신규 메시지** 상태에서 (a) `extract_session(uid, sid)` → `{"skipped": True, "reason": "insufficient"}`, (b) `extract_session(uid, sid, force=True)` → 추출 실행(`extracted` 키 존재·extracted_until 전진) 단정 2건. 기존 케이스·cleanup 관행 유지.

Run: `python scripts/self_model_extraction_test.py`
Expected: 기존 16 + 신규 2 = `PASS=18 FAIL=0` (기존 케이스 수가 다르면 FAIL=0 만 게이트).

- [ ] **Step 7: 커밋**

```bash
git add backend/domain/user_intelligence/hub/services/consult_interview_bank.py backend/core/llm/client.py backend/domain/user_intelligence/hub/services/self_model_extraction_service.py backend/scripts/interview_bank_test.py backend/scripts/self_model_extraction_test.py
git commit -m "feat(sp8b): 인터뷰 문항 은행·플래너 LLM·상담 프롬프트 개정·force 추출"
```

---

### Task 2: 그래프 확장 — plan·extract 노드 + 커버리지 state + 즉시 추출

**Files:**
- Modify: `backend/domain/user_intelligence/spokes/infra/consult_graph.py` (state 확장·plan/extract 노드·guidance 주입)
- Modify: `backend/domain/user_intelligence/hub/services/consult_service.py` (`_planner`·`_extract_round` 심)
- Modify(테스트): `backend/scripts/consult_graph_test.py` (FakeService 확장 + 신규 7 검증)
- Modify(테스트): stream_sse를 fake streamer로 실행하는 기존 스위트에 fake planner 주입(아래 Step 4)

**Interfaces:**
- Consumes: Task 1 — `ALL_AXES`·`first_uncovered`·`axis_label`·`probe_hint`·`LlmClient.plan_interview`·`extract_session(force=True)`.
- Produces: `ConsultState`에 `coverage: dict`·`mode: str`·`plan: dict`·`round_done: bool` 채널. 서비스 심 `_planner(coverage, recent, message) -> dict`·`_extract_round(user_id, session_id) -> None`. SSE 이벤트 `{"type": "self_model_updated"}`(Task 3 프론트가 소비).

- [ ] **Step 1: 그래프 테스트 확장 (실패 확인용)**

`backend/scripts/consult_graph_test.py` 수정 — FakeService에 플래너·추출 심 기본값 추가(기존 케이스는 커버리지 미완이라 추출이 안 돌아 무영향), 신규 검증 추가. FakeService `__init__` 에 추가:

```python
        self.extract_calls: list[tuple[str, str]] = []

        async def default_planner(coverage, recent, message):
            return {"mode": "interview", "newly_covered": [], "focus_axis": None, "focus_hint": None}

        self._planner = default_planner

        async def default_extract_round(user_id, session_id):
            self.extract_calls.append((user_id, session_id))

        self._extract_round = default_extract_round
```

`run()` 말미(기존 체크 뒤)에 추가. 상단 import 에 `from domain.user_intelligence.spokes.infra.consult_graph import ConsultState`는 불필요 — `build_consult_graph`만. state 검사는 MemorySaver 로 한다(파일 상단에 `from langgraph.checkpoint.memory import MemorySaver` 추가).

```python
    # --- SP-8b 인터뷰 검증 ---
    from domain.user_intelligence.hub.services.consult_interview_bank import ALL_AXES

    # 커버리지 병합 + 인터뷰 지침 주입
    svc4 = FakeService()

    async def planner4(coverage, recent, message):
        return {"mode": "interview", "newly_covered": ["R", "I"], "focus_axis": "A", "focus_hint": "표현 활동 각도"}

    svc4._planner = planner4
    graph4 = build_consult_graph(svc4, MemorySaver())
    cfg4 = {"configurable": {"thread_id": "t4"}}
    await collect(graph4, {"user_id": "u1", "session_id": "s4", "message": "네"}, cfg4)
    st4 = await graph4.aget_state(cfg4)
    check("plan 커버리지 병합", st4.values.get("coverage") == {"R": True, "I": True}, str(st4.values.get("coverage")))
    sys4 = svc4.seen_messages[0]["content"]
    check("인터뷰 지침 주입", "예술형" in sys4 and "표현 활동 각도" in sys4, sys4[-200:])

    # 경청 모드
    svc5 = FakeService()

    async def planner5(coverage, recent, message):
        return {"mode": "listening", "newly_covered": [], "focus_axis": None, "focus_hint": None}

    svc5._planner = planner5
    graph5 = build_consult_graph(svc5)
    await collect(graph5, {"user_id": "u1", "session_id": "s5", "message": "요즘 너무 힘들어"}, {"configurable": {"thread_id": "t5"}})
    check("경청 모드 지침", "경청" in svc5.seen_messages[0]["content"], svc5.seen_messages[0]["content"][-200:])

    # 플래너 실패 → 정적 폴백(첫 미커버 축)
    svc6 = FakeService()

    async def planner6(coverage, recent, message):
        raise RuntimeError("plan fail")

    svc6._planner = planner6
    graph6 = build_consult_graph(svc6)
    chunks6 = await collect(graph6, {"user_id": "u1", "session_id": "s6", "message": "hi"}, {"configurable": {"thread_id": "t6"}})
    check("플랜 실패 폴백 지침", "현실형" in svc6.seen_messages[0]["content"], svc6.seen_messages[0]["content"][-200:])
    check("플랜 실패에도 스트림 정상", any(c.get("type") == "delta" for c in chunks6), str(chunks6))

    # 전 축 커버 → 즉시 추출 + 이벤트 + round_done
    svc7 = FakeService()

    async def planner7(coverage, recent, message):
        return {"mode": "interview", "newly_covered": list(ALL_AXES), "focus_axis": None, "focus_hint": None}

    svc7._planner = planner7
    graph7 = build_consult_graph(svc7, MemorySaver())
    cfg7 = {"configurable": {"thread_id": "t7"}}
    chunks7 = await collect(graph7, {"user_id": "u7", "session_id": "s7", "message": "응"}, cfg7)
    check("라운드 완료 즉시 추출", svc7.extract_calls == [("u7", "s7")], str(svc7.extract_calls))
    check("self_model_updated 방출", any(c.get("type") == "self_model_updated" for c in chunks7), str(chunks7))
    st7 = await graph7.aget_state(cfg7)
    check("round_done 설정", st7.values.get("round_done") is True, str(st7.values.get("round_done")))

    # 같은 스레드 다음 턴 — 재추출 없음
    chunks7b = await collect(graph7, {"user_id": "u7", "session_id": "s7", "message": "더 얘기하자"}, cfg7)
    check("round_done 재추출 스킵", len(svc7.extract_calls) == 1 and not any(c.get("type") == "self_model_updated" for c in chunks7b), str(svc7.extract_calls))

    # 추출 실패 — 비치명(이벤트 없음·round_done 미설정)
    svc8 = FakeService()
    svc8._planner = planner7

    async def boom_extract(user_id, session_id):
        raise RuntimeError("extract fail")

    svc8._extract_round = boom_extract
    graph8 = build_consult_graph(svc8, MemorySaver())
    cfg8 = {"configurable": {"thread_id": "t8"}}
    chunks8 = await collect(graph8, {"user_id": "u8", "session_id": "s8", "message": "응"}, cfg8)
    check("추출 실패 비치명", not any(c.get("type") == "self_model_updated" for c in chunks8)
          and (await graph8.aget_state(cfg8)).values.get("round_done") is not True, str(chunks8))
```

- [ ] **Step 2: 실패 확인**

Run: `python scripts/consult_graph_test.py`
Expected: 신규 체크들 FAIL(plan 노드 미존재 — coverage 미병합·지침 미주입 등). 기존 9는 PASS 유지.

- [ ] **Step 3: 그래프 확장 구현**

`consult_graph.py`:

(1) import 추가:
```python
from domain.user_intelligence.hub.services.consult_interview_bank import (
    ALL_AXES,
    axis_label,
    first_uncovered,
    probe_hint,
)
```

(2) `ConsultState`에 채널 추가:
```python
    coverage: dict          # 축 코드 → True(신호 확보) — 체크포인터로 턴 간 지속
    mode: str               # interview | listening
    plan: dict              # 이번 턴 계획 {focus_axis, focus_hint}
    round_done: bool        # 이번 세션 라운드 완료·즉시 추출 수행됨
```

(3) `build_consult_graph` 안에 plan·extract 노드 추가, respond 에 guidance 주입.

```python
    async def plan(state: ConsultState) -> dict:
        coverage = dict(state.get("coverage") or {})
        try:
            p = await service._planner(coverage, state["recent"], state["message"])
        except Exception as e:  # 플랜 실패 — 정적 폴백(미커버 첫 축·interview)으로 상담을 지속한다.
            logger.warning(f"인터뷰 플랜 실패(정적 폴백): {e}")
            p = {"mode": "interview", "newly_covered": [], "focus_axis": None, "focus_hint": None}
        for code in p.get("newly_covered") or []:
            if code in ALL_AXES:
                coverage[code] = True
        mode = p.get("mode") if p.get("mode") in ("interview", "listening") else "interview"
        focus = p.get("focus_axis") if p.get("focus_axis") in ALL_AXES else None
        if focus is None and mode != "listening":
            focus = first_uncovered(coverage)
        hint = p.get("focus_hint") or (probe_hint(focus) if focus else None)
        return {"coverage": coverage, "mode": mode, "plan": {"focus_axis": focus, "focus_hint": hint}}
```

respond 의 messages 조립 직전에 guidance 삽입(기존 `messages = consult_context.build_llm_messages(...)` 한 줄을 아래로 교체):
```python
        guidance = ""
        if state.get("mode") == "listening":
            guidance = "\n\n[이번 턴 지침] 사용자가 고민을 꺼냈다. 조사 질문을 멈추고 경청·공감·반영에 집중하라."
        else:
            plan_info = state.get("plan") or {}
            focus = plan_info.get("focus_axis")
            if focus:
                guidance = (
                    f"\n\n[이번 턴 지침] 대화 흐름을 살리면서 '{axis_label(focus)}' 성향을 알 수 있는 "
                    f"질문을 자연스럽게 하나 던져라. 참고 각도: {plan_info.get('focus_hint') or ''}"
                )
        messages = consult_context.build_llm_messages(
            state["system_content"] + guidance, state.get("summary"), state["recent"], state["message"]
        )
```

```python
    async def extract(state: ConsultState) -> dict:
        if state.get("round_done"):
            return {}
        coverage = state.get("coverage") or {}
        if not all(coverage.get(c) for c in ALL_AXES):
            return {}
        writer = get_stream_writer()
        try:
            await service._extract_round(state["user_id"], state["session_id"])
        except Exception as e:  # 즉시 추출 실패는 치명적이지 않다 — 일일 배치가 수거한다.
            logger.warning(f"라운드 즉시 추출 실패(일일 배치 수거): {e}")
            return {}
        writer({"type": "self_model_updated"})
        return {"round_done": True}
```

(4) 엣지 재배선(기존 4개 엣지 교체):
```python
    g.add_node("plan", plan)
    g.add_node("extract", extract)
    g.add_edge(START, "prepare")
    g.add_edge("prepare", "plan")
    g.add_edge("plan", "respond")
    g.add_edge("respond", "persist")
    g.add_edge("persist", "extract")
    g.add_edge("extract", END)
```

- [ ] **Step 4: ConsultService 심 추가**

`consult_service.py`:
- import 추가: `from domain.user_intelligence.hub.services.self_model_extraction_service import SelfModelExtractionService`
- `__init__` 의 `self._summarizer = self._default_summarizer` 아래:
```python
        self._planner = self._default_planner
        self._extract_round = self._default_extract_round
```
- `_default_summarizer` 아래 메서드 2개:
```python
    async def _default_planner(self, coverage: dict, recent: list[dict], message: str) -> dict:
        llm = LlmClient(api_key=self._api_key, model=self._model)
        return await llm.plan_interview(coverage, recent, message)

    async def _default_extract_round(self, user_id: str, session_id: str) -> None:
        """라운드 완료 즉시 추출 — 독립 세션에서 force 로 임계 우회."""
        async with AsyncSessionLocal() as db:
            await SelfModelExtractionService(db).extract_session(user_id, session_id, force=True)
```
- **기존 스위트 주입** — `stream_sse`를 fake streamer 로 실행하는 기존 테스트(최소 `consult_service_test.py`의 svc·svc2·svc3, 그 외 스위트는 실행해 보고 실LLM 플래너를 타는 곳만)에 각 서비스 생성 직후 1줄 주입:
```python
        async def fake_planner(coverage, recent, message):
            return {"mode": "interview", "newly_covered": [], "focus_axis": "I", "focus_hint": None}

        svc._planner = fake_planner
```
(커버리지가 안 차므로 추출은 안 돈다 — 기존 단정 무영향. 테스트 수정은 이 주입에 한정.)

- [ ] **Step 5: 전체 확인**

Run: `python scripts/consult_graph_test.py`
Expected: `결과: PASS=19 FAIL=0` (기존 9 + 신규 10).

Run (각 FAIL=0): `python scripts/consult_service_test.py; python scripts/consult_stream_test.py; python scripts/consult_endpoint_test.py; python scripts/consult_context_test.py; python scripts/consult_session_repository_test.py; python scripts/consult_session_models_import_test.py; python scripts/consult_extract_repo_test.py`

- [ ] **Step 6: 커밋**

```bash
git add backend/domain/user_intelligence/spokes/infra/consult_graph.py backend/domain/user_intelligence/hub/services/consult_service.py backend/scripts/consult_graph_test.py backend/scripts/consult_service_test.py
git commit -m "feat(sp8b): 그래프에 인터뷰 plan·extract 노드 — 커버리지 추적·경청 전환·라운드 완료 즉시 추출"
```
(다른 스위트 파일도 주입 수정했다면 함께 명시 스테이징.)

---

### Task 3: 프론트 SSE 이벤트 + §8 문서 개정

**Files:**
- Modify: `www.yeotaeho.kr/src/lib/api/consult.ts` (`streamConsult` onSelfModelUpdated)
- Modify: `www.yeotaeho.kr/src/components/features/consult/ConsultView.tsx` (이벤트 → self-model 쿼리 무효화)
- Modify: `backend/docs/DATA_COLLECTION_SOURCES_GUIDE_V3.md` (§8 원칙 개정)

**Interfaces:**
- Consumes: Task 2 SSE `{"type": "self_model_updated"}` · SelfModelPanel 쿼리키 `["self-model", profile?.id]`.
- Produces: 없음(말단).

- [ ] **Step 1: consult.ts — 콜백 추가**

`streamConsult` 시그니처 마지막에 선택 콜백 추가(기존 호출부 하위호환):
```typescript
export async function streamConsult(
  sessionId: string,
  message: string,
  onDelta: (text: string) => void,
  signal?: AbortSignal,
  onSelfModelUpdated?: () => void,
): Promise<void> {
```
파서 분기(`obj.type === 'delta'` 라인 아래):
```typescript
        if (obj.type === 'self_model_updated') onSelfModelUpdated?.();
```

- [ ] **Step 2: ConsultView — 무효화 연결**

`ConsultView.tsx`:
- import 추가: `import { useQueryClient } from "@tanstack/react-query";`
- 컴포넌트에 `const queryClient = useQueryClient();` 와 `const profile = useStore((s) => s.profile);`(이미 있으면 재사용).
- `streamConsult(sessionId, text, (delta) => {...})` 호출을 5인자로 확장:
```tsx
      await streamConsult(
        sessionId,
        text,
        (delta) => {
          setMessages((m) =>
            m.map((msg) =>
              msg.id === assistantId ? { ...msg, text: msg.text + delta } : msg,
            ),
          );
        },
        undefined,
        () => queryClient.invalidateQueries({ queryKey: ["self-model", profile?.id] }),
      );
```

- [ ] **Step 3: §8 문서 개정**

`backend/docs/DATA_COLLECTION_SOURCES_GUIDE_V3.md` §8 표의 두 행을 교체.

수집 방법 행:
```markdown
| **수집 방법** | 사용자가 입력한 자연어 대화. **외부 API·크롤 아님**(1인칭 자기보고). 흥미·일하는 방식은 AI가 설문(워크넷·O*NET 문항 풀) 근거로 **능동적으로 질문**(하이브리드 인터뷰 — 고민이 나오면 경청 전환). 민감 주제(트라우마·건강·가족사 등)는 캐묻지 않음 |
```
추출 방법 행:
```markdown
| **추출 방법** | 일별 배치(`_job_self_model_extract`, 10:00 KST) 증분 추출 + **조사 라운드 완료 시 즉시 추출**(11축 커버리지 충족 시 대화 중 1회, SSE 로 성향 지도 실시간 갱신) |
```

- [ ] **Step 4: 타입 검증**

Run: `cd www.yeotaeho.kr; pnpm exec tsc --noEmit`
Expected: 출력 없음(0 에러).

- [ ] **Step 5: 커밋**

```bash
git add www.yeotaeho.kr/src/lib/api/consult.ts www.yeotaeho.kr/src/components/features/consult/ConsultView.tsx backend/docs/DATA_COLLECTION_SOURCES_GUIDE_V3.md
git commit -m "feat(sp8b): self_model_updated SSE 로 성향 지도 실시간 갱신 + §8 능동 조사 원칙 개정"
```

---

## 최종 검증 (whole-branch)

- [ ] 백엔드 (cwd `backend/`, 각 FAIL=0): `interview_bank_test` · `consult_graph_test` · 7개 consult 스위트 · `self_model_extraction_test` · `self_model_user_edits_test`.
- [ ] 프론트 `pnpm exec tsc --noEmit` 0.
- [ ] 리뷰 게이트 — code-reviewer whole-branch → Codex `--base <시작 ref> --scope branch`.
- [ ] SP-8a 이월 재조명 여부 점검(강등 트리거 분류·커넥션 풀·Linux 검증) — 이번 범위 밖이면 렛저에 유지.
