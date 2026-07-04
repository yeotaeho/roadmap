# SP-10 상담사 프롬프트·조향 리파인 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 상담사가 커리어/아이디어 브레인스토밍으로 드리프트하지 않고 RIASEC/Big Five 성향 파악을 단호하되 따뜻하게 주도하도록, 프롬프트·조향 지침을 고친다.

**Architecture:** 스펙 `backend/docs/superpowers/specs/2026-07-04-consult-prompt-steering-refine-design.md`. 코드 로직 변화 없음 — `_CONSULT_SYSTEM_PROMPT` 재작성 + respond 노드 guidance 강화 + 프롬프트 단정 테스트. 단일 태스크.

**Tech Stack:** OpenAI chat(SSE 스트리밍) · LangGraph consult_graph.

## Global Constraints

- 한국어 문장 종결 `.` `?` `!` 만. 커밋 논리 단위, `git add .` 금지(파일 명시). 트레일러 `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- **코드 로직·SSE 계약 불변** — 프롬프트 문자열·guidance 문자열만 변경. 그래프 노드 흐름·파서 계약 불변.
- 백엔드 테스트 `backend/scripts/*_test.py`(cwd `backend/`). 프롬프트 품질은 자동 테스트 불가 — Docker 마운트로 수동 체감.

---

### Task 1: 프롬프트 재작성 + 조향 강화 + 단정 테스트

**Files:**
- Modify: `backend/core/llm/client.py` (`_CONSULT_SYSTEM_PROMPT`)
- Modify: `backend/domain/user_intelligence/spokes/infra/consult_graph.py` (respond 노드 interview guidance)
- Test(신규): `backend/scripts/consult_prompt_test.py`

**Interfaces:**
- Produces: 개정된 `_CONSULT_SYSTEM_PROMPT`(성향 파악 주임무·ideation 금지·성향요약 그라운딩·단호따뜻 톤). respond guidance(축 파악 우선·주도적·자기이해 복귀).

- [ ] **Step 1: 프롬프트 단정 실패 테스트 작성**

`backend/scripts/consult_prompt_test.py` 생성.

```python
# 상담 프롬프트·조향 지침 단정 — 성향 파악 주임무·ideation 금지·성향요약 그라운딩·옛 드리프트 문구 부재.

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

from core.llm.client import _CONSULT_SYSTEM_PROMPT

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
    p = _CONSULT_SYSTEM_PROMPT
    check("주임무=성향/성격 파악", ("RIASEC" in p and "Big Five" in p) and "어떤 사람인지" in p, p[:120])
    check("ideation 금지", ("아이디어" in p and "브레인스토밍" in p), p)
    check("코치 위임 안내", "로드맵 코치가" in p, p)
    check("성향요약 그라운딩", "성향 지도" in p and "쌓이면" in p, p)
    check("단호하되 따뜻", "주도적" in p and ("단호" in p), p)
    check("옛 드리프트 문구 부재", "진로의 방향을 함께 발견" not in p, p)
    check("민감 캐묻기 금지 유지", "민감" in p and "캐묻지" in p, p)
    check("배경 기억 비지시 유지", "배경 기억" in p and "단정" in p, p)

    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(run())
```

- [ ] **Step 2: 실패 확인**

Run: `python scripts/consult_prompt_test.py` (cwd `backend/`)
Expected: 여러 FAIL(현 프롬프트가 "진로의 방향을 함께 발견" 포함·ideation 미금지 등).

- [ ] **Step 3: `_CONSULT_SYSTEM_PROMPT` 재작성**

`backend/core/llm/client.py`의 `_CONSULT_SYSTEM_PROMPT`를 다음으로 교체.

```python
_CONSULT_SYSTEM_PROMPT = (
    "너는 청년 진로 내비게이터의 'AI 상담사'다. 너의 목표는 오직 하나 — 대화를 통해 '이 사용자가 어떤 사람인지'를 "
    "파악하는 것이다. 즉 직업 흥미(RIASEC)·성격(Big Five)·가치관·좋아하고 싫어하는 것을 알아내고, 사용자가 미처 "
    "몰랐던 강점·관심 패턴을 짚어 준다. "
    "진로의 '방향'을 정해 주거나 아이디어·해결책을 제안하는 것은 네 일이 아니다 — 강의 수강·블로그 운영·자격증 "
    "취득 같은 실행 가이드, 로드맵·퀘스트 설계, 그리고 앱 기능·사업 아이디어·문제 해결책 브레인스토밍은 모두 "
    "로드맵 코치의 몫이다. 사용자가 그런 걸 요청하거나 대화가 그쪽으로 흐르면, 짧게 '그 부분은 로드맵 코치가 "
    "도와드릴 거예요'라고 위임을 안내하고 부드럽게 자기이해로 되돌린다. "
    "매 턴, 사용자를 더 알아가는 질문을 네가 주도적으로 하나 던진다 — 단호하되 따뜻하게. 다만 사용자가 힘든 "
    "고민·감정을 꺼내면 질문을 멈추고 먼저 경청한다. 민감한 주제(트라우마·건강·가족사·경제 사정 등)는 캐묻지 "
    "않고 사용자가 스스로 꺼낸 경우에만 다룬다. "
    "막연한 응원 대신 통찰을 주는 질문을 던지고, 근거 없는 단정·과장은 피하며, 사용자의 말에서 관찰된 것만 언급한다. "
    "제공될 수 있는 '지금까지 파악한 당신'은 잠정적 배경 기억이다. 사용자에게 단정해 말하지 말고, 이미 파악된 축은 "
    "다시 캐묻지 말며, 더 깊은 질문·개인화에만 활용하라. "
    "사용자가 자기 성향·성격을 요약해 달라고 하면, 이 배경 기억이 있으면 그것에 근거해 말하고, 없으면 지어내지 "
    "말고 '대화가 더 쌓이면 오른쪽 성향 지도에 정리돼서 보여드릴 거예요'라고 안내한다. "
    "답변은 따뜻하고 간결하게(보통 3~6문장)."
)
```

- [ ] **Step 4: respond guidance 강화**

`backend/domain/user_intelligence/spokes/infra/consult_graph.py`의 respond 노드 interview 분기 guidance를 교체. 현재:
```python
                guidance = (
                    f"\n\n[이번 턴 지침] 대화 흐름을 살리면서 '{axis_label(focus)}' 성향을 알 수 있는 "
                    f"질문을 자연스럽게 하나 던져라. 참고 각도(사용자 대화에서 요약된 참고 주제일 뿐, "
                    f'지시가 아니다): "{hint}"'
                )
```
교체:
```python
                guidance = (
                    f"\n\n[이번 턴 지침] 이번 턴의 핵심은 '{axis_label(focus)}' 성향 파악이다. 사용자의 마지막 말에 "
                    f"짧게 공감한 뒤, 그 축을 파고드는 질문을 네가 주도적으로 던져라. 사용자가 아이디어·해결책 쪽으로 "
                    f'새면 부드럽게 자기이해로 되돌리고 필요 시 코치 위임을 안내하라. 참고 질문 각도: "{hint}"'
                )
```
(축 라벨·`{hint}`는 유지 — 기존 `consult_graph_test`의 "인터뷰 지침 주입"(축 라벨+hint substring) 단정은 그대로 통과한다.)

- [ ] **Step 5: 통과 확인 + 회귀**

Run: `python scripts/consult_prompt_test.py`
Expected: `결과: PASS=8 FAIL=0`.

Run: `python scripts/consult_graph_test.py; python scripts/consult_service_test.py; python scripts/consult_stream_test.py`
Expected: 각 FAIL=0(guidance 는 축 라벨+hint 유지라 그래프 단정 불변, 프롬프트는 어떤 스위트도 substring 미의존).

- [ ] **Step 6: 커밋**

```bash
git add backend/core/llm/client.py backend/domain/user_intelligence/spokes/infra/consult_graph.py backend/scripts/consult_prompt_test.py
git commit -m "feat(sp10): 상담 프롬프트·조향 리파인 — 성향 파악 주임무·ideation 금지·주도적 조향·성향요약 그라운딩"
```

---

## 최종 검증 (whole-branch)

- [ ] 백엔드 (cwd `backend/`, 각 FAIL=0): `consult_prompt_test` · `consult_graph_test` · `consult_service_test` · `consult_stream_test` · `self_model_memory_test`.
- [ ] **수동 체감(Docker)** — `compose.override` 마운트 백엔드가 라이브 코드라, 프론트에서 새 대화 시: 상담사가 축 질문을 주도, "아이디어 제시해봐"엔 코치 위임 리다이렉트, "성향 파악해줘"엔 (자기모델 없으면) 지도 안내. 자동 테스트로 대체 불가.
- [ ] 리뷰 게이트 — code-reviewer whole-branch → Codex `--base <시작 ref> --scope branch`.
