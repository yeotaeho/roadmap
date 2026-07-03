# SP-5 Big Five 성격 5요인 추출·시각화 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** RIASEC(SP-4) 인프라를 일반화(`blend_axes`)해 Big Five 5요인(OCEAN)을 같은 LLM 호출에서 0~100 채점하고(K=8 강한 shrinkage), 상담실 우측 패널에 5개 가로 막대(신경성은 정서안정성으로 표시층 flip)로 시각화한다.

**Architecture:** 스펙 `backend/docs/superpowers/specs/2026-07-03-big-five-extraction-design.md` 기준. 2태스크 — (1) 백엔드(블렌딩 일반화·프롬프트·파서·추출·병합·테스트), (2) 프론트(bigFive 타입·5막대). `big_five`는 JSONB라 DDL 불필요. N은 canonical 저장, flip은 프론트 표시층에서만. Big Five는 top_codes 없음.

**Tech Stack:** FastAPI · SQLAlchemy 2.0 async · OpenAI(chat JSON mode) · Next.js/TS/React 19 · TanStack Query.

## Global Constraints

- 한국어 문장 종결은 `.` `?` `!` 만 — `:` 로 끝내지 않는다.
- 새 소스 파일 첫 줄은 한 줄 한국어 역할 주석.
- 커밋은 논리 단위별. `git add .` 금지 — 파일 명시, `.omc/`·`.superpowers/`·`__pycache__` 제외. 커밋 메시지 끝 `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>` 트레일러.
- 백엔드 테스트는 `backend/scripts/*_test.py` 관행(PASS/FAIL check, `python scripts/<name>_test.py`). 통합은 dev Neon — 시드 cleanup.
- 프론트 검증은 `www.yeotaeho.kr` 에서 `pnpm exec tsc --noEmit` 0 에러.
- Big Five 코드·순서: `O C E A N`(개방·성실·외향·우호·신경). 상수 `BIGFIVE_CODES=("O","C","E","A","N")`, `BIGFIVE_SHRINK_K=8`.
- **N은 canonical(높을수록 신경성) 저장** — 정서안정성(100−N) 변환은 프론트 표시층에서만.
- `blend_riasec` 출력 계약(top_codes 포함) 불변 — SP-3 임베딩·설명이 읽는다.
- DB 마이그레이션 없음(big_five JSONB 형태 코드 전용). 기존 null 행 하위호환.

---

### Task 1: 백엔드 Big Five 점수화 (블렌딩 일반화·프롬프트·파서·추출·병합)

**Files:**
- Modify: `backend/domain/user_intelligence/hub/services/riasec_scoring.py` (`blend_axes` 추출·`blend_big_five`·상수)
- Modify: `backend/core/llm/client.py` (`_SELF_MODEL_EXTRACT_SYSTEM_PROMPT`·`_parse_self_model_extract`)
- Modify: `backend/domain/user_intelligence/hub/services/self_model_extraction_service.py` (incoming.big_five)
- Modify: `backend/domain/user_intelligence/hub/services/self_model_service.py` (merge 분기 일반화)
- Test(신규): `backend/scripts/big_five_scoring_test.py` (순수)
- Modify(테스트): `backend/scripts/riasec_scoring_test.py`(회귀 확인)·`self_model_extract_parse_test.py`·`self_model_extraction_test.py`

**Interfaces:**
- Consumes: SP-4 `blend_riasec`·`_axis`·`_clamp`·`NEUTRAL`·merge 분기.
- Produces:
  - `riasec_scoring.blend_axes(existing, window_scores, window_conf, codes, shrink_k) -> {"scores":{int}, "raw":{float}, "weights":{float}}` · `blend_big_five(existing, ws, wc) -> 같은 형태(top_codes 없음)` · 상수 `BIGFIVE_CODES`·`BIGFIVE_SHRINK_K`.
  - `_parse_self_model_extract(raw)` 반환에 `big_five_scores:{5키 0~100}`·`big_five_axis_confidence:{5키 0~1}` 추가.
  - `merge_structured`: `incoming["big_five"]`에 `window_scores` 있으면 `blend_big_five` 결과 저장.

- [ ] **Step 1: `blend_big_five` 순수 실패 테스트 작성**

`backend/scripts/big_five_scoring_test.py` 생성.

```python
# Big Five 5축 블렌딩·K=8 shrinkage·하위호환 순수 테스트

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from domain.user_intelligence.hub.services.riasec_scoring import (
    BIGFIVE_CODES,
    BIGFIVE_SHRINK_K,
    blend_big_five,
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


def _full(v):
    return {c: v for c in BIGFIVE_CODES}


def run() -> int:
    check("코드 OCEAN", BIGFIVE_CODES == ("O", "C", "E", "A", "N"))
    check("K=8", BIGFIVE_SHRINK_K == 8)

    hi = {**_full(50), "C": 90, "N": 20}
    conf = {**_full(0.2), "C": 0.9, "N": 0.8}
    r = blend_big_five(None, hi, conf)
    check("첫관측 raw=window", r["raw"]["C"] == 90 and r["raw"]["N"] == 20, str(r["raw"]))
    check("top_codes 없음", "top_codes" not in r, str(r.keys()))
    check("5축 존재", set(r["scores"].keys()) == set(BIGFIVE_CODES))
    # K=8 이므로 첫 관측(weight 0.9)은 RIASEC(K=4)보다 더 강하게 50 방향 shrink
    expected_C = round(50 + (90 - 50) * min(1, 0.9 / BIGFIVE_SHRINK_K))
    check("K=8 shrinkage C", r["scores"]["C"] == expected_C, f'{r["scores"]["C"]} vs {expected_C}')

    # 반복 누적 8회면 weight 커져 C 가 raw(90)에 근접
    acc = None
    for _ in range(8):
        acc = blend_big_five(acc, hi, conf)
    check("반복 누적 C 상승", acc["scores"]["C"] >= 80, str(acc["scores"]["C"]))
    check("반복 누적 N 하강", acc["scores"]["N"] <= 30, str(acc["scores"]["N"]))

    # 하위호환 — existing None(빈 big_five)
    check("None existing raw=window", blend_big_five(None, hi, conf)["raw"]["C"] == 90)
    # 옛/누락 형태(raw/weights 없음) → 50·0 취급
    check("누락형태 하위호환", blend_big_five({"foo": 1}, hi, conf)["raw"]["C"] == 90)

    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(run())
```

- [ ] **Step 2: 실패 확인**

Run: `python scripts/big_five_scoring_test.py` (cwd `backend/`)
Expected: `ImportError: cannot import name 'BIGFIVE_CODES'`.

- [ ] **Step 3: `riasec_scoring.py` 일반화**

파일 상단 상수 아래에 Big Five 상수 추가.

```python
BIGFIVE_CODES = ("O", "C", "E", "A", "N")
BIGFIVE_SHRINK_K = 8.0   # 성격은 흥미보다 짧은 대화에서 신뢰도 낮음 → RIASEC(4)보다 강한 shrinkage
```

`blend_riasec` 를 다음으로 교체(핵심을 `blend_axes` 로 추출, `blend_riasec`·`blend_big_five` 는 래퍼).

```python
def blend_axes(
    existing: dict | None, window_scores: dict, window_conf: dict, codes: tuple, shrink_k: float
) -> dict:
    """축 집합에 대한 confidence 가중 증분 평균 + shrinkage. 순수·결정론.

    반환: {"scores": {int, shrink 적용}, "raw": {float}, "weights": {float}}.
    existing 의 raw/weights 가 없거나 옛 형태여도 중립 50·0 으로 취급(하위호환).
    """
    prev_raw = existing.get("raw") if isinstance(existing, dict) else None
    prev_w = existing.get("weights") if isinstance(existing, dict) else None

    raw: dict[str, float] = {}
    weights: dict[str, float] = {}
    scores: dict[str, int] = {}
    for c in codes:
        s_prev = _axis(prev_raw, c, NEUTRAL)
        w_prev = _axis(prev_w, c, 0.0)
        s_win = _clamp(_axis(window_scores, c, NEUTRAL), 0.0, 100.0)
        w_win = _clamp(_axis(window_conf, c, 0.0), 0.0, 1.0)
        w_new = w_prev + w_win
        s_new = (s_prev * w_prev + s_win * w_win) / w_new if w_new > 0 else NEUTRAL
        raw[c] = s_new
        weights[c] = w_new
        shrunk = NEUTRAL + (s_new - NEUTRAL) * min(1.0, w_new / shrink_k)
        scores[c] = int(round(_clamp(shrunk, 0.0, 100.0)))
    return {"scores": scores, "raw": raw, "weights": weights}


def blend_riasec(existing_riasec: dict | None, window_scores: dict, window_conf: dict) -> dict:
    """RIASEC 6축 블렌딩 + top_codes 파생(점수 순위 상위 2, 55 초과). 하위호환 유지."""
    out = blend_axes(existing_riasec, window_scores, window_conf, RIASEC_CODES, SHRINK_K)
    ranked = sorted(RIASEC_CODES, key=lambda c: out["scores"][c], reverse=True)
    out["top_codes"] = [c for c in ranked if out["scores"][c] > TOP_MIN][:2]
    return out


def blend_big_five(existing_big_five: dict | None, window_scores: dict, window_conf: dict) -> dict:
    """Big Five 5축(OCEAN) 블렌딩. N은 canonical(높을수록 신경성) — flip 없음. top_codes 없음."""
    return blend_axes(existing_big_five, window_scores, window_conf, BIGFIVE_CODES, BIGFIVE_SHRINK_K)
```

파일 첫 줄 주석을 `# RIASEC·Big Five 축 점수 블렌딩 — confidence 가중 증분 평균 + shrinkage(순수·결정론)` 로 갱신.

- [ ] **Step 4: 순수 테스트 통과 + RIASEC 회귀 확인**

Run: `python scripts/big_five_scoring_test.py`
Expected: `결과: PASS=10 FAIL=0`.

Run: `python scripts/riasec_scoring_test.py`
Expected: `FAIL=0`(blend_riasec 래퍼가 기존 계약·top_codes 유지).

- [ ] **Step 5: 파서 실패 테스트 갱신**

`backend/scripts/self_model_extract_parse_test.py` 의 `run()` 첫 케이스(ok) 입력에 big_five 필드를 추가하고 단정 추가. `ok = _parse_self_model_extract(json.dumps({...}))` 의 딕셔너리에 다음 두 키를 추가한다.

```python
        "big_five_scores": {"O": 70, "C": 120, "E": -5, "A": 55, "N": 40},
        "big_five_axis_confidence": {"O": 0.6, "C": 1.4, "E": 0.1, "A": 0.5, "N": 0.3},
```

그리고 첫 케이스 단정들 뒤에 추가.

```python
    check("big_five 5키", set(ok["big_five_scores"].keys()) == {"O", "C", "E", "A", "N"}, str(ok["big_five_scores"]))
    check("big_five 클램프", ok["big_five_scores"]["C"] == 100 and ok["big_five_scores"]["E"] == 0, str(ok["big_five_scores"]))
    check("big_five conf 클램프", ok["big_five_axis_confidence"]["C"] == 1.0)
```

누락 케이스(partial) 뒤에 추가(big_five 미제공 시 전 축 50·0).

```python
    check("big_five 누락 축 50", partial["big_five_scores"]["O"] == 50, str(partial["big_five_scores"]))
    check("big_five 누락 conf 0", partial["big_five_axis_confidence"]["O"] == 0.0)
```

- [ ] **Step 6: 실패 확인**

Run: `python scripts/self_model_extract_parse_test.py`
Expected: `[FAIL] big_five 5키 ...`(파서가 아직 big_five 미반환 → KeyError 또는 실패).

- [ ] **Step 7: 프롬프트·파서 구현**

`core/llm/client.py` `_SELF_MODEL_EXTRACT_SYSTEM_PROMPT` 를 다음으로 교체(RIASEC 부분 유지 + Big Five 추가).

```python
_SELF_MODEL_EXTRACT_SYSTEM_PROMPT = (
    "너는 청년 진로 상담사와 사용자의 대화에서 사용자의 '자기모델' 신호를 추출하는 분석기다. "
    "대화에서 드러난 (1) 직업 흥미 RIASEC 6축을 각각 0~100 점수로 채점하라(R현실·I탐구·A예술·S사회·E진취·C관습). "
    "(2) 성격 Big Five 5축도 각각 0~100 점수로 채점하라(O개방성·C성실성·E외향성·A우호성·N신경성). "
    "N(신경성)은 원지표대로 채점하되(높을수록 정서적으로 예민·반응적) 병리적으로 단정하지 마라. "
    "행동·구체적 일화 근거를 명시적 자기규정('저는 사회형이에요')보다 높게 가중하라. "
    "특정 축의 근거가 부족하면 그 축은 50(중립) 근처로 보수적으로 채점하고 axis_confidence 를 낮게 매겨라(억지 추정 금지). "
    "top_codes 는 네가 정하지 마라(점수에서 파생된다). "
    "(3) 한 줄 자기서사, (4) 근거(호불호·가치관·제약·포부·스킬 신호)도 뽑아라. "
    "민감정보(트라우마·개인적 아픔·건강·가정사 등)는 사용자가 스스로 드러낸 것만 is_sensitive=true 로 표시하고, "
    "능동적으로 캐묻거나 추론하지 마라. "
    'JSON 객체만 출력하라. 형식: {"riasec_scores": {"R":<0~100>,"I":<0~100>,"A":<0~100>,"S":<0~100>,"E":<0~100>,"C":<0~100>}, '
    '"riasec_axis_confidence": {"R":<0~1>,"I":<0~1>,"A":<0~1>,"S":<0~1>,"E":<0~1>,"C":<0~1>}, '
    '"big_five_scores": {"O":<0~100>,"C":<0~100>,"E":<0~100>,"A":<0~100>,"N":<0~100>}, '
    '"big_five_axis_confidence": {"O":<0~1>,"C":<0~1>,"E":<0~1>,"A":<0~1>,"N":<0~1>}, '
    '"narrative": <문자열 또는 null>, '
    '"evidence": [{"dimension": <"like"|"dislike"|"value"|"constraint"|"sensitive"|"aspiration"|"skill_signal"|"other">, '
    '"polarity": <"like"|"dislike"|"neutral"|null>, "content": <근거 문장>, '
    '"confidence": <0~1>, "is_sensitive": <bool>}...]}.'
)
```

`_RIASEC_CODES` 정의 아래에 상수 추가.

```python
_BIGFIVE_CODES = ("O", "C", "E", "A", "N")
```

`_parse_self_model_extract` 에서 riasec 6축 파싱 블록 바로 뒤(narrative 파싱 앞)에 big_five 파싱을 추가하고, 반환 dict에 두 키를 추가한다. riasec 파싱 루프 아래에 삽입.

```python
    bf_scores_raw = obj.get("big_five_scores")
    bf_conf_raw = obj.get("big_five_axis_confidence")
    big_five_scores: dict[str, int] = {}
    big_five_axis_confidence: dict[str, float] = {}
    for c in _BIGFIVE_CODES:
        try:
            s = float(bf_scores_raw.get(c)) if isinstance(bf_scores_raw, dict) else 50.0
        except (TypeError, ValueError):
            s = 50.0
        big_five_scores[c] = int(round(max(0.0, min(100.0, s))))
        try:
            cf = float(bf_conf_raw.get(c)) if isinstance(bf_conf_raw, dict) else 0.0
        except (TypeError, ValueError):
            cf = 0.0
        big_five_axis_confidence[c] = max(0.0, min(1.0, cf))
```

그리고 `return {...}` 딕셔너리에 두 키를 추가한다.

```python
    return {
        "riasec_scores": scores,
        "riasec_axis_confidence": axis_conf,
        "big_five_scores": big_five_scores,
        "big_five_axis_confidence": big_five_axis_confidence,
        "narrative": narrative,
        "evidence": evidence,
    }
```

또한 `_empty()`(비JSON·비dict 폴백) 반환에도 두 키를 추가한다.

```python
    def _empty() -> dict:
        return {
            "riasec_scores": {c: 50 for c in _RIASEC_CODES},
            "riasec_axis_confidence": {c: 0.0 for c in _RIASEC_CODES},
            "big_five_scores": {c: 50 for c in _BIGFIVE_CODES},
            "big_five_axis_confidence": {c: 0.0 for c in _BIGFIVE_CODES},
            "narrative": None,
            "evidence": [],
        }
```

- [ ] **Step 8: 파서 테스트 통과 확인**

Run: `python scripts/self_model_extract_parse_test.py`
Expected: `FAIL=0`.

- [ ] **Step 9: 추출 서비스 배선**

`self_model_extraction_service.py` `extract_session` 의 incoming 매핑을 교체.

```python
        result = await self._extractor(new_msgs)
        svc = SelfModelService(self.db)
        r_conf = result["riasec_axis_confidence"]
        bf_conf = result["big_five_axis_confidence"]
        axis_confidence = {
            "riasec": sum(r_conf.values()) / len(r_conf) if r_conf else 0.0,
            "big_five": sum(bf_conf.values()) / len(bf_conf) if bf_conf else 0.0,
        }
        if result["narrative"]:
            axis_confidence["narrative_summary"] = max(axis_confidence["riasec"], NARRATIVE_DEFAULT_CONFIDENCE)
        incoming = {
            "riasec": {"window_scores": result["riasec_scores"], "window_conf": r_conf},
            "big_five": {"window_scores": result["big_five_scores"], "window_conf": bf_conf},
            "narrative_summary": result["narrative"],
            "axis_confidence": axis_confidence,
        }
        await svc.upsert_structured(user_id, incoming, SOURCE)
        n_ev = await svc.append_evidence(user_id, result["evidence"], SOURCE)
        await self.coach_repo.update_extracted(session_id, cutoff)
        return {"extracted": len(new_msgs), "evidence": n_ev, "riasec": True}
```

- [ ] **Step 10: 병합 분기 일반화**

`self_model_service.py` 상단 임포트를 `from domain.user_intelligence.hub.services.riasec_scoring import blend_big_five, blend_riasec` 로 갱신.

`merge_structured` 의 riasec 전용 분기를 두 축 일반화로 교체.

```python
        if axis in ("riasec", "big_five") and isinstance(inc, dict) and "window_scores" in inc:
            # 점수 블렌딩 — user_form 이 아닌 대화 추출만. user_form 은 아래 일반 규칙(overwrite) 유지.
            if source != SOURCE_USER_FORM:
                # user_form 으로 명시 입력된 축은 코치 추출 blend 가 잠식하지 않는다.
                if existing_source == SOURCE_USER_FORM and base.get(axis) is not None:
                    continue
                existing_axis = base.get(axis) if isinstance(base.get(axis), dict) else None
                blender = blend_riasec if axis == "riasec" else blend_big_five
                result[axis] = blender(existing_axis, inc["window_scores"], inc["window_conf"])
                merged_conf[axis] = sum(inc["window_conf"].values()) / len(inc["window_conf"]) if inc["window_conf"] else 0.0
                continue
```

- [ ] **Step 11: 추출 통합 테스트 갱신**

`self_model_extraction_test.py` 의 fake extractor 반환에 big_five 필드를 추가한다. `fake_extractor` 반환 딕셔너리에 다음 두 키 추가.

```python
                "big_five_scores": {"O": 60, "C": 85, "E": 45, "A": 70, "N": 25},
                "big_five_axis_confidence": {"O": 0.4, "C": 0.9, "E": 0.3, "A": 0.6, "N": 0.7},
```

`narrative_only_extractor` 반환에도 추가(전 축 50·0).

```python
                "big_five_scores": {c: 50 for c in ("O", "C", "E", "A", "N")},
                "big_five_axis_confidence": {c: 0.0 for c in ("O", "C", "E", "A", "N")},
```

riasec 반영 단정 뒤에 big_five 단정 추가.

```python
        big_five = model["bigFive"]
        check("big_five scores 존재", isinstance(big_five, dict) and "scores" in big_five, str(big_five))
        check("big_five C 상승", big_five["scores"]["C"] >= big_five["scores"]["E"], str(big_five["scores"]))
```

(`model` 은 `get_self_model` 반환 — `bigFive` 키. get_self_model 은 `model["big_five"]` 를 `bigFive` 로 셰이핑한다.)

- [ ] **Step 12: 통합 테스트 실행**

Run: `python scripts/self_model_extraction_test.py`
Expected: `FAIL=0`.

- [ ] **Step 13: 회귀 실행**

Run: `python scripts/self_model_merge_test.py; python scripts/self_model_repository_test.py; python scripts/self_model_endpoint_test.py; python scripts/self_model_embed_candidacy_test.py; python scripts/recommend_explain_service_test.py`
Expected: 각 FAIL=0. (임베딩·추천은 `riasec.top_codes` 만 읽어 big_five 무영향. merge 테스트가 big_five overwrite 를 단정하면 blend 형태로 갱신.)

- [ ] **Step 14: 커밋**

```bash
git add backend/domain/user_intelligence/hub/services/riasec_scoring.py backend/core/llm/client.py backend/domain/user_intelligence/hub/services/self_model_extraction_service.py backend/domain/user_intelligence/hub/services/self_model_service.py backend/scripts/big_five_scoring_test.py backend/scripts/self_model_extract_parse_test.py backend/scripts/self_model_extraction_test.py
git commit -m "feat(sp5): Big Five 5축 점수화 — blend_axes 일반화·K=8 shrinkage·canonical N·같은 호출 채점"
```

---

### Task 2: 프론트 Big Five 5막대 (신경성→정서안정성 표시 flip)

**Files:**
- Modify: `www.yeotaeho.kr/src/lib/api/selfModel.ts` (bigFive 타입)
- Modify: `www.yeotaeho.kr/src/components/features/consult/SelfModelPanel.tsx` (placeholder → 5막대)

**Interfaces:**
- Consumes: Task 1 이 서빙하는 `selfModel.bigFive = {scores:{O,C,E,A,N}} | null`.
- Produces: 없음(말단 UI).

- [ ] **Step 1: `selfModel.ts` bigFive 타입**

`RiasecScores` 인터페이스 아래에 추가.

```typescript
export interface BigFiveScores {
  O: number; C: number; E: number; A: number; N: number;
}
```

`SelfModelLive` 의 `bigFive` 필드 타입을 교체.

```typescript
  bigFive: { scores: BigFiveScores } | null;
```

(`fetchSelfModel` 의 `bigFive: m.bigFive ?? null` 매핑은 그대로.)

- [ ] **Step 2: SelfModelPanel — placeholder를 5막대로 교체**

`SelfModelPanel.tsx` 상단 상수(`POSITIVE_DIMS` 아래)에 Big Five 축 정의를 추가.

```tsx
const BF_AXES: { key: "O" | "C" | "E" | "A" | "N"; label: string; flip?: boolean }[] = [
  { key: "O", label: "개방성" },
  { key: "C", label: "성실성" },
  { key: "E", label: "외향성" },
  { key: "A", label: "우호성" },
  { key: "N", label: "정서안정성", flip: true },
];
```

컴포넌트 본문에서 `riasec` 파생 근처에 `bigFive` 파생을 추가.

```tsx
  const bigFive = data?.bigFive ?? null;
```

기존 placeholder `<div>`(약 118~120행, "대화가 쌓이면 성격 5요인(Big Five)도 여기에 나타나요.")를 다음으로 교체.

```tsx
      {bigFive?.scores ? (
        <div className="mt-1 space-y-1.5">
          <p className="text-[11px] font-semibold text-slate-600 dark:text-slate-400">성격 5요인</p>
          {BF_AXES.map(({ key, label, flip }) => {
            const v = flip ? 100 - (bigFive.scores.N ?? 50) : (bigFive.scores[key] ?? 50);
            return (
              <div key={key} className="flex items-center gap-2">
                <span className="w-14 shrink-0 text-[11px] text-slate-600 dark:text-slate-300">{label}</span>
                <div className="relative h-2 flex-1 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-700">
                  <div className="absolute left-1/2 top-0 h-full w-px bg-slate-300 dark:bg-slate-600" aria-hidden />
                  <div className="h-full rounded-full bg-indigo-500" style={{ width: `${v}%` }} />
                </div>
              </div>
            );
          })}
          <p className="text-[10px] text-slate-400 dark:text-slate-500">가운데 선은 중립(파악 중)이에요.</p>
        </div>
      ) : (
        <div className="mt-1 rounded-xl border border-dashed border-slate-200 px-3 py-2.5 text-[11px] leading-relaxed text-slate-400 dark:border-slate-700 dark:text-slate-500">
          대화가 쌓이면 성격 5요인(Big Five)도 여기에 나타나요.
        </div>
      )}
```

(정서안정성 막대만 `100 − N` 으로 표시 — flip은 여기서만. 나머지 4축은 원값. 파일 첫 줄 주석의 "성격 placeholder" 를 "성격 5요인" 으로 갱신.)

- [ ] **Step 3: 타입 검증**

Run: `cd www.yeotaeho.kr; pnpm exec tsc --noEmit`
Expected: 출력 없음(0 에러).

- [ ] **Step 4: 커밋**

```bash
git add www.yeotaeho.kr/src/lib/api/selfModel.ts www.yeotaeho.kr/src/components/features/consult/SelfModelPanel.tsx
git commit -m "feat(sp5): 상담실 패널에 Big Five 5막대(정서안정성 표시 flip) — placeholder 교체"
```

---

## 최종 검증 (whole-branch)

- [ ] 백엔드 회귀 (cwd `backend/`, 각 FAIL=0):
```bash
python scripts/big_five_scoring_test.py
python scripts/riasec_scoring_test.py
python scripts/self_model_extract_parse_test.py
python scripts/self_model_extraction_test.py
python scripts/self_model_merge_test.py
python scripts/self_model_repository_test.py
python scripts/self_model_endpoint_test.py
python scripts/self_model_embed_candidacy_test.py
python scripts/recommend_explain_service_test.py
```
- [ ] 프론트 `cd www.yeotaeho.kr; pnpm exec tsc --noEmit` 0 에러.
- [ ] 리뷰 게이트 — code-reviewer 에이전트 whole-branch → Codex `/codex:review --base <시작 ref> --scope branch`.
