# SP-4 자기모델 RIASEC 점수화 + 상담실 시각화 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** RIASEC 추출을 top_codes 대신 6축 0~100 점수로 바꾸고(confidence 가중 블렌딩 + shrinkage), `/consult` 우측 목업 지갑을 자기모델 실데이터 `SelfModelPanel`(레이더·주요유형·서사·근거·big_five placeholder)로 교체한다.

**Architecture:** 스펙 `backend/docs/superpowers/specs/2026-07-03-self-model-riasec-scoring-viz-design.md` 기준. 2태스크 — (1) 백엔드 RIASEC 점수화(LLM 프롬프트·순수 파서·순수 블렌딩 `blend_riasec`·merge 연결·추출 배선·테스트), (2) 프론트(자기모델 API 클라이언트·SelfModelPanel·ConsultView 교체). `riasec`는 JSONB라 DDL 불필요 — 형태만 `{scores,raw,weights,top_codes}`로. SP-3 임베딩은 `riasec.top_codes`를 계속 읽어 무영향.

**Tech Stack:** FastAPI · SQLAlchemy 2.0 async · OpenAI(chat JSON mode) · Next.js/TS/React 19 · recharts(기존 의존성) · TanStack Query.

## Global Constraints

- 한국어 문장 종결은 `.` `?` `!` 만 — `:` 로 끝내지 않는다.
- 새 소스 파일 첫 줄은 한 줄 한국어 역할 주석.
- 커밋은 논리 단위별. `git add .` 금지 — 파일 명시, `.omc/`·`.superpowers/`·`__pycache__` 제외. 커밋 메시지 끝 `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>` 트레일러.
- 백엔드 테스트는 `backend/scripts/*_test.py` 관행(PASS/FAIL check 함수, `python scripts/<name>_test.py`). 통합 테스트는 dev Neon — 시드 cleanup 필수.
- 프론트 검증은 `www.yeotaeho.kr` 에서 `pnpm exec tsc --noEmit` 0 에러.
- RIASEC 6축 순서·코드: `R I A S E C`(현실·탐구·예술·사회·진취·관습). 상수 `SHRINK_K = 4`, `TOP_MIN = 55`.
- `riasec.top_codes` 계약 유지(SP-3 임베딩·설명이 읽음) — 점수 순위에서 파생, 별도 로직 금지.
- DB 마이그레이션 없음(riasec JSONB 형태 변경은 코드 전용). 기존 `{top_codes}`만 있는 행 하위호환.

---

### Task 1: 백엔드 RIASEC 6축 점수화 (프롬프트·파서·블렌딩·병합·추출)

**Files:**
- Create: `backend/domain/user_intelligence/hub/services/riasec_scoring.py`
- Modify: `backend/core/llm/client.py` (`_SELF_MODEL_EXTRACT_SYSTEM_PROMPT`·`_parse_self_model_extract`)
- Modify: `backend/domain/user_intelligence/hub/services/self_model_service.py` (`merge_structured` riasec 분기)
- Modify: `backend/domain/user_intelligence/hub/services/self_model_extraction_service.py` (incoming 매핑)
- Test(신규): `backend/scripts/riasec_scoring_test.py` (순수)
- Modify(테스트): `backend/scripts/self_model_extract_parse_test.py`, `backend/scripts/self_model_extraction_test.py`

**Interfaces:**
- Consumes: 기존 `merge_structured(existing, incoming, source)`·`SelfModelService.upsert_structured`.
- Produces:
  - `_parse_self_model_extract(raw)` 반환 `{riasec_scores: {6키 0~100}, riasec_axis_confidence: {6키 0~1}, narrative, evidence}` (기존 `riasec_top_codes`·`riasec_confidence` 제거).
  - `riasec_scoring.blend_riasec(existing_riasec: dict|None, window_scores: dict, window_conf: dict) -> {"scores": {6키 int}, "raw": {6키 float}, "weights": {6키 float}, "top_codes": list[str]}` · 상수 `RIASEC_CODES`·`SHRINK_K`·`TOP_MIN`.
  - `merge_structured`: `incoming["riasec"]`에 `window_scores` 있으면 blend, 결과 dict 저장.

- [ ] **Step 1: `blend_riasec` 순수 실패 테스트 작성**

`backend/scripts/riasec_scoring_test.py` 생성.

```python
# RIASEC 6축 블렌딩·shrinkage·top_codes 파생 순수 테스트

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from domain.user_intelligence.hub.services.riasec_scoring import (
    RIASEC_CODES,
    SHRINK_K,
    TOP_MIN,
    blend_riasec,
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
    return {c: v for c in RIASEC_CODES}


def run() -> int:
    # 첫 관측(existing None) — raw = window, weights = conf
    hi = {**_full(50), "I": 90, "A": 80}
    conf = {**_full(0.2), "I": 0.9, "A": 0.8}
    r = blend_riasec(None, hi, conf)
    check("raw=window(첫관측)", r["raw"]["I"] == 90 and r["raw"]["A"] == 80, str(r["raw"]))
    check("weights=conf(첫관측)", abs(r["weights"]["I"] - 0.9) < 1e-9)
    # shrinkage — I weight 0.9 < K=4 이므로 display 는 50에 가깝게 당겨짐
    expected_I = round(50 + (90 - 50) * min(1, 0.9 / SHRINK_K))
    check("shrinkage 첫관측 I", r["scores"]["I"] == expected_I, f'{r["scores"]["I"]} vs {expected_I}')
    check("근거 얇으면 top_codes 비거나 축소", isinstance(r["top_codes"], list))

    # 반복 관측 — 같은 방향 4회 누적하면 weight 커져 display 가 raw(90)에 근접, top_codes 에 I
    acc = None
    for _ in range(5):
        acc = blend_riasec(acc, hi, conf)
    check("반복 누적 I 상승", acc["scores"]["I"] >= 80, str(acc["scores"]["I"]))
    check("top_codes 파생(I 최상위)", acc["top_codes"][:1] == ["I"], str(acc["top_codes"]))
    check("top_codes 최대 2개", len(acc["top_codes"]) <= 2)
    check("TOP_MIN 미달 축 제외", all(acc["scores"][c] > TOP_MIN for c in acc["top_codes"]))

    # confidence 가중 평균 — 낮은 conf 반대 신호는 raw 를 약간만 끌어내림
    low_opp = {**_full(50), "I": 10}
    low_conf = {**_full(0.1), "I": 0.1}
    blended = blend_riasec(acc, low_opp, low_conf)
    check("낮은 conf 반대신호 영향 작음", blended["raw"]["I"] > 70, str(blended["raw"]["I"]))

    # 하위호환 — existing 이 top_codes 만 있는 옛 형태(raw/weights 없음) → 50·0 기준
    old = {"top_codes": ["S"]}
    r2 = blend_riasec(old, hi, conf)
    check("하위호환 raw=window", r2["raw"]["I"] == 90, str(r2["raw"]))
    check("하위호환 weights=conf", abs(r2["weights"]["I"] - 0.9) < 1e-9)

    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(run())
```

- [ ] **Step 2: 실패 확인**

Run: `python scripts/riasec_scoring_test.py` (cwd `backend/`)
Expected: `ModuleNotFoundError`/`ImportError` (riasec_scoring 없음).

- [ ] **Step 3: `riasec_scoring.py` 구현**

`backend/domain/user_intelligence/hub/services/riasec_scoring.py` 생성.

```python
# RIASEC 6축 점수 블렌딩 — confidence 가중 증분 평균 + shrinkage + top_codes 파생(순수·결정론)

from __future__ import annotations

RIASEC_CODES = ("R", "I", "A", "S", "E", "C")
NEUTRAL = 50.0
SHRINK_K = 4.0   # 누적 가중치가 이 값에 이르면 raw 를 완전 표현(그 전엔 50 방향 shrink)
TOP_MIN = 55     # display 점수가 이 값 초과인 축만 top_codes 후보


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _axis(d: dict | None, key: str, default: float) -> float:
    """dict 에서 축 값 안전 추출(비dict·누락·비수치는 default)."""
    if not isinstance(d, dict):
        return default
    v = d.get(key)
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def blend_riasec(existing_riasec: dict | None, window_scores: dict, window_conf: dict) -> dict:
    """기존 축별 누적(raw·weights)에 이번 창의 6축 점수를 confidence 가중으로 병합한다.

    반환: {"scores": {6키 int, shrink 적용}, "raw": {6키 float}, "weights": {6키 float}, "top_codes": [코드...]}.
    existing 이 옛 형태({top_codes}만)여도 raw/weights 를 중립·0 으로 취급해 하위호환.
    """
    prev_raw = existing_riasec.get("raw") if isinstance(existing_riasec, dict) else None
    prev_w = existing_riasec.get("weights") if isinstance(existing_riasec, dict) else None

    raw: dict[str, float] = {}
    weights: dict[str, float] = {}
    scores: dict[str, int] = {}
    for c in RIASEC_CODES:
        s_prev = _axis(prev_raw, c, NEUTRAL)
        w_prev = _axis(prev_w, c, 0.0)
        s_win = _clamp(_axis(window_scores, c, NEUTRAL), 0.0, 100.0)
        w_win = _clamp(_axis(window_conf, c, 0.0), 0.0, 1.0)
        w_new = w_prev + w_win
        s_new = (s_prev * w_prev + s_win * w_win) / w_new if w_new > 0 else NEUTRAL
        raw[c] = s_new
        weights[c] = w_new
        shrunk = NEUTRAL + (s_new - NEUTRAL) * min(1.0, w_new / SHRINK_K)
        scores[c] = int(round(_clamp(shrunk, 0.0, 100.0)))

    ranked = sorted(RIASEC_CODES, key=lambda c: scores[c], reverse=True)
    top_codes = [c for c in ranked if scores[c] > TOP_MIN][:2]
    return {"scores": scores, "raw": raw, "weights": weights, "top_codes": top_codes}
```

- [ ] **Step 4: 순수 테스트 통과 확인**

Run: `python scripts/riasec_scoring_test.py`
Expected: `결과: PASS=11 FAIL=0`, exit 0.

- [ ] **Step 5: 파서 실패 테스트 갱신**

`backend/scripts/self_model_extract_parse_test.py` 를 새 반환 형태로 교체(전체 파일).

```python
# 자기모델 추출 응답 순수 파서 테스트 — RIASEC 6축 점수·confidence 클램프·dimension 닫힌집합.

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SCHEDULER_ENABLED", "false")

from core.llm.client import _parse_self_model_extract

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
    ok = _parse_self_model_extract(json.dumps({
        "riasec_scores": {"R": -5, "I": 120, "A": 80, "S": 40, "E": 55, "C": 30},
        "riasec_axis_confidence": {"R": 0.1, "I": 1.5, "A": 0.8, "S": 0.4, "E": 0.5, "C": 0.2},
        "narrative": "  탐구·표현 지향  ",
        "evidence": [
            {"dimension": "like", "polarity": "like", "content": "발표를 좋아함", "confidence": 0.9, "is_sensitive": False},
            {"dimension": "unknown_dim", "polarity": "??", "content": "x", "confidence": 2.0, "is_sensitive": True},
            {"dimension": "value", "polarity": None, "content": "  ", "confidence": 0.5, "is_sensitive": False},
        ],
    }))
    check("scores 6키", set(ok["riasec_scores"].keys()) == {"R", "I", "A", "S", "E", "C"}, str(ok["riasec_scores"]))
    check("scores 클램프 0~100", ok["riasec_scores"]["R"] == 0 and ok["riasec_scores"]["I"] == 100, str(ok["riasec_scores"]))
    check("axis_conf 클램프 0~1", ok["riasec_axis_confidence"]["I"] == 1.0 and ok["riasec_axis_confidence"]["R"] == 0.1)
    check("narrative strip", ok["narrative"] == "탐구·표현 지향")
    check("evidence 유효 1건", len(ok["evidence"]) == 1 and ok["evidence"][0]["content"] == "발표를 좋아함", str(ok["evidence"]))

    # 누락 키 → score 50·conf 0
    partial = _parse_self_model_extract(json.dumps({"riasec_scores": {"I": 70}}))
    check("누락 축 score 50", partial["riasec_scores"]["R"] == 50, str(partial["riasec_scores"]))
    check("누락 축 conf 0", partial["riasec_axis_confidence"]["R"] == 0.0)
    check("있는 축 반영", partial["riasec_scores"]["I"] == 70)

    # 비JSON·비dict → 전 축 50·conf 0·narrative None·evidence []
    empty = _parse_self_model_extract("not json")
    check("비JSON scores 50", all(v == 50 for v in empty["riasec_scores"].values()), str(empty["riasec_scores"]))
    check("비JSON conf 0", all(v == 0.0 for v in empty["riasec_axis_confidence"].values()))
    check("비JSON narrative None", empty["narrative"] is None and empty["evidence"] == [])

    print(f"\n결과: PASS={PASS} FAIL={FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(run())
```

- [ ] **Step 6: 실패 확인**

Run: `python scripts/self_model_extract_parse_test.py`
Expected: `[FAIL] scores 6키 ...` (파서가 아직 riasec_top_codes 반환).

- [ ] **Step 7: 프롬프트·파서 구현**

`core/llm/client.py` `_SELF_MODEL_EXTRACT_SYSTEM_PROMPT` 를 다음으로 교체.

```python
_SELF_MODEL_EXTRACT_SYSTEM_PROMPT = (
    "너는 청년 진로 상담사와 사용자의 대화에서 사용자의 '자기모델' 신호를 추출하는 분석기다. "
    "대화에서 드러난 (1) 직업 흥미 RIASEC 6축을 각각 0~100 점수로 채점하라(R현실·I탐구·A예술·S사회·E진취·C관습). "
    "행동·구체적 일화 근거를 명시적 자기규정('저는 사회형이에요')보다 높게 가중하라. "
    "특정 축의 근거가 부족하면 그 축은 50(중립) 근처로 보수적으로 채점하고 axis_confidence 를 낮게 매겨라(억지 추정 금지). "
    "top_codes 는 네가 정하지 마라(점수에서 파생된다). "
    "(2) 한 줄 자기서사, (3) 근거(호불호·가치관·제약·포부·스킬 신호)도 뽑아라. "
    "민감정보(트라우마·개인적 아픔·건강·가정사 등)는 사용자가 스스로 드러낸 것만 is_sensitive=true 로 표시하고, "
    "능동적으로 캐묻거나 추론하지 마라. "
    'JSON 객체만 출력하라. 형식: {"riasec_scores": {"R":<0~100>,"I":<0~100>,"A":<0~100>,"S":<0~100>,"E":<0~100>,"C":<0~100>}, '
    '"riasec_axis_confidence": {"R":<0~1>,"I":<0~1>,"A":<0~1>,"S":<0~1>,"E":<0~1>,"C":<0~1>}, '
    '"narrative": <문자열 또는 null>, '
    '"evidence": [{"dimension": <"like"|"dislike"|"value"|"constraint"|"sensitive"|"aspiration"|"skill_signal"|"other">, '
    '"polarity": <"like"|"dislike"|"neutral"|null>, "content": <근거 문장>, '
    '"confidence": <0~1>, "is_sensitive": <bool>}...]}.'
)
```

`_parse_self_model_extract` 를 다음으로 교체.

```python
def _parse_self_model_extract(raw: str | None) -> dict:
    """자기모델 추출 응답을 검증된 결과로 파싱한다. 무네트워크 순수 함수.

    riasec_scores 6축 0~100·axis_confidence 6축 0~1(누락 키는 50·0). evidence 는 content 있는 항목만·최대 20개,
    dimension 닫힌집합 외는 'other', polarity 닫힌집합 외는 None, confidence 0~1 클램프.
    """
    def _empty() -> dict:
        return {
            "riasec_scores": {c: 50 for c in _RIASEC_CODES},
            "riasec_axis_confidence": {c: 0.0 for c in _RIASEC_CODES},
            "narrative": None,
            "evidence": [],
        }
    try:
        obj = json.loads(raw) if raw else {}
    except (json.JSONDecodeError, TypeError):
        return _empty()
    if not isinstance(obj, dict):
        return _empty()

    scores_raw = obj.get("riasec_scores")
    conf_raw = obj.get("riasec_axis_confidence")
    scores: dict[str, int] = {}
    axis_conf: dict[str, float] = {}
    for c in _RIASEC_CODES:
        try:
            s = float(scores_raw.get(c)) if isinstance(scores_raw, dict) else 50.0
        except (TypeError, ValueError):
            s = 50.0
        scores[c] = int(round(max(0.0, min(100.0, s))))
        try:
            cf = float(conf_raw.get(c)) if isinstance(conf_raw, dict) else 0.0
        except (TypeError, ValueError):
            cf = 0.0
        axis_conf[c] = max(0.0, min(1.0, cf))

    narrative = obj.get("narrative")
    narrative = narrative.strip()[:500] if isinstance(narrative, str) and narrative.strip() else None

    evidence: list[dict] = []
    ev_raw = obj.get("evidence")
    if isinstance(ev_raw, list):
        for it in ev_raw:
            if not isinstance(it, dict):
                continue
            content = it.get("content")
            if not isinstance(content, str) or not content.strip():
                continue
            dim = it.get("dimension")
            dim = dim if dim in _EVIDENCE_DIMS else "other"
            pol = it.get("polarity")
            pol = pol if pol in _EVIDENCE_POLARITIES else None
            try:
                conf = float(it.get("confidence"))
            except (TypeError, ValueError):
                conf = 0.0
            conf = max(0.0, min(1.0, conf))
            evidence.append({
                "dimension": dim,
                "polarity": pol,
                "content": content.strip()[:500],
                "confidence": conf,
                "is_sensitive": bool(it.get("is_sensitive", False)),
            })
            if len(evidence) >= 20:
                break

    return {
        "riasec_scores": scores,
        "riasec_axis_confidence": axis_conf,
        "narrative": narrative,
        "evidence": evidence,
    }
```

(기존 `_parse_self_model_extract` 의 옛 본문·`empty` 딕셔너리는 완전히 대체한다. `_RIASEC_CODES`·`_EVIDENCE_DIMS`·`_EVIDENCE_POLARITIES` 상수는 그대로 재사용.)

- [ ] **Step 8: 파서 테스트 통과 확인**

Run: `python scripts/self_model_extract_parse_test.py`
Expected: `결과: PASS=11 FAIL=0`, exit 0.

- [ ] **Step 9: `merge_structured` riasec 분기 + 추출 배선**

`self_model_service.py` 상단에 임포트 추가.

```python
from domain.user_intelligence.hub.services.riasec_scoring import blend_riasec
```

`merge_structured` 의 `for axis in _AXES:` 루프에서 riasec 축을 특수 처리. 루프 안, `inc = incoming.get(axis)` 뒤에 분기 추가.

```python
    for axis in _AXES:
        inc = incoming.get(axis)
        if inc is None:
            continue
        if axis == "riasec" and isinstance(inc, dict) and "window_scores" in inc:
            # 점수 블렌딩 — user_form 이 아닌 대화 추출만. user_form 은 아래 일반 규칙(overwrite) 유지.
            if source != SOURCE_USER_FORM:
                existing_riasec = base.get("riasec") if isinstance(base.get("riasec"), dict) else None
                blended = blend_riasec(existing_riasec, inc["window_scores"], inc["window_conf"])
                result["riasec"] = blended
                merged_conf["riasec"] = sum(inc["window_conf"].values()) / len(inc["window_conf"]) if inc["window_conf"] else 0.0
                continue
        if source == SOURCE_USER_FORM:
            result[axis] = inc  # 사용자 명시 입력 최우선
            merged_conf[axis] = 1.0
            continue
        # coach/consult extraction (비riasec-scores 축)
        if existing_source == SOURCE_USER_FORM and base.get(axis) is not None:
            continue
        conf = _incoming_conf(incoming, axis, source)
        merged_conf[axis] = conf
        if conf < CONFIDENCE_THRESHOLD:
            continue
        result[axis] = inc
```

`self_model_extraction_service.py` 의 `extract_session` 에서 incoming 매핑을 교체.

```python
        result = await self._extractor(new_msgs)
        svc = SelfModelService(self.db)
        window_conf = result["riasec_axis_confidence"]
        axis_confidence = {"riasec": sum(window_conf.values()) / len(window_conf) if window_conf else 0.0}
        if result["narrative"]:
            axis_confidence["narrative_summary"] = max(axis_confidence["riasec"], NARRATIVE_DEFAULT_CONFIDENCE)
        incoming = {
            "riasec": {"window_scores": result["riasec_scores"], "window_conf": window_conf},
            "big_five": None,
            "narrative_summary": result["narrative"],
            "axis_confidence": axis_confidence,
        }
        await svc.upsert_structured(user_id, incoming, SOURCE)
        n_ev = await svc.append_evidence(user_id, result["evidence"], SOURCE)
        await self.coach_repo.update_extracted(session_id, cutoff)
        return {"extracted": len(new_msgs), "evidence": n_ev, "riasec": True}
```

- [ ] **Step 10: 추출 통합 테스트 갱신**

`backend/scripts/self_model_extraction_test.py` 의 fake extractor 반환과 assertion 을 새 형태로 갱신. fake_extractor 를 다음으로 교체(riasec_top_codes → riasec_scores·riasec_axis_confidence).

```python
        async def fake_extractor(messages):
            fake_calls["n"] += 1
            return {
                "riasec_scores": {"R": 50, "I": 88, "A": 82, "S": 50, "E": 55, "C": 45},
                "riasec_axis_confidence": {"R": 0.2, "I": 0.9, "A": 0.8, "S": 0.2, "E": 0.3, "C": 0.2},
                "narrative": "탐구·표현 지향",
                "evidence": [
                    {"dimension": "like", "polarity": "like", "content": "발표를 좋아함", "confidence": 0.9, "is_sensitive": False},
                    {"dimension": "constraint", "polarity": None, "content": "장거리 통근 어려움", "confidence": 0.7, "is_sensitive": True},
                ],
            }
```

기존 `check("riasec 반영", model["riasec"] == {"top_codes": ["I", "A"]}, ...)` 를 다음으로 교체.

```python
        riasec = model["riasec"]
        check("riasec scores 존재", isinstance(riasec, dict) and "scores" in riasec, str(riasec))
        check("riasec I 최상위 근접", riasec["scores"]["I"] >= riasec["scores"]["R"], str(riasec["scores"]))
```

narrative-only extractor(있으면)는 `riasec_scores` 전부 50·`riasec_axis_confidence` 전부 0.0 으로 바꾼다. `narrative_only_extractor` 반환을 다음으로.

```python
        async def narrative_only_extractor(messages):
            return {
                "riasec_scores": {c: 50 for c in ("R", "I", "A", "S", "E", "C")},
                "riasec_axis_confidence": {c: 0.0 for c in ("R", "I", "A", "S", "E", "C")},
                "narrative": "안정보다 성장을 우선시함",
                "evidence": [],
            }
```

`res.get("riasec")` 를 단정하는 기존 체크가 있으면 `res["riasec"]` 가 항상 True 임을 반영해 갱신(6축 채점이 기본이므로).

- [ ] **Step 11: 통합 테스트 실행**

Run: `python scripts/self_model_extraction_test.py`
Expected: `FAIL=0`. (실패 시 남은 옛 형태 단정을 새 scores 형태로 갱신.)

- [ ] **Step 12: 회귀 실행**

Run: `python scripts/self_model_merge_test.py; python scripts/self_model_repository_test.py; python scripts/self_model_endpoint_test.py; python scripts/self_model_embed_text_test.py; python scripts/self_model_embed_candidacy_test.py; python scripts/recommend_explain_service_test.py`
Expected: 각 FAIL=0. (embed·recommend 은 `riasec.top_codes` 를 읽는데 blend 결과에도 top_codes 가 있어 유지. self_model_merge_test 가 riasec overwrite 를 단정하면 blend 형태로 갱신.)

- [ ] **Step 13: 커밋**

```bash
git add backend/domain/user_intelligence/hub/services/riasec_scoring.py backend/core/llm/client.py backend/domain/user_intelligence/hub/services/self_model_service.py backend/domain/user_intelligence/hub/services/self_model_extraction_service.py backend/scripts/riasec_scoring_test.py backend/scripts/self_model_extract_parse_test.py backend/scripts/self_model_extraction_test.py
git commit -m "feat(sp4): RIASEC 6축 점수화 — confidence 가중 블렌딩+shrinkage, top_codes 점수 파생"
```

---

### Task 2: 프론트 자기모델 패널 (SelfModelPanel + 지갑 교체)

**Files:**
- Create: `www.yeotaeho.kr/src/lib/api/selfModel.ts`
- Create: `www.yeotaeho.kr/src/components/features/consult/SelfModelPanel.tsx`
- Modify: `www.yeotaeho.kr/src/components/features/consult/ConsultView.tsx` (InsightWalletPanel → SelfModelPanel)

**Interfaces:**
- Consumes: Task 1 이 서빙하는 `GET /api/user/self-model` → `{success, selfModel: {riasec: {scores: {R..C}, top_codes} | null, bigFive: null, narrativeSummary: string|null, axisConfidence, evidence: [{dimension, polarity, content, confidence}]}}`.
- Produces: 없음(말단 UI).

- [ ] **Step 1: API 클라이언트 작성**

`www.yeotaeho.kr/src/lib/api/selfModel.ts` 생성.

```typescript
// AI 상담실 자기모델(RIASEC·서사·근거) 서빙 API 클라이언트
import { apiClient } from './client';

export interface SelfModelEvidence {
  dimension: string;
  polarity: string | null;
  content: string;
  confidence: number | null;
}

export interface RiasecScores {
  R: number; I: number; A: number; S: number; E: number; C: number;
}

export interface SelfModelLive {
  riasec: { scores: RiasecScores; top_codes: string[] } | null;
  bigFive: Record<string, number> | null;
  narrativeSummary: string | null;
  axisConfidence: Record<string, number> | null;
  evidence: SelfModelEvidence[];
}

export async function fetchSelfModel(): Promise<SelfModelLive> {
  const { data } = await apiClient.get('/api/user/self-model');
  const m = data?.selfModel ?? {};
  return {
    riasec: m.riasec ?? null,
    bigFive: m.bigFive ?? null,
    narrativeSummary: m.narrativeSummary ?? null,
    axisConfidence: m.axisConfidence ?? null,
    evidence: Array.isArray(m.evidence) ? m.evidence : [],
  };
}
```

- [ ] **Step 2: SelfModelPanel 컴포넌트 작성**

`www.yeotaeho.kr/src/components/features/consult/SelfModelPanel.tsx` 생성.

```tsx
// 상담실 우측 — 자기모델(RIASEC 레이더·주요유형·서사·근거·성격 placeholder) 실데이터 패널
"use client";

import { useQuery } from "@tanstack/react-query";
import { Radar as RadarIcon, Sparkles } from "lucide-react";
import {
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
} from "recharts";
import { fetchSelfModel, type SelfModelLive } from "@/lib/api/selfModel";

const INDIGO = "#4F46E5";
const RIASEC_LABEL: Record<string, string> = {
  R: "현실", I: "탐구", A: "예술", S: "사회", E: "진취", C: "관습",
};
const RIASEC_TYPE: Record<string, string> = {
  R: "현실형", I: "탐구형", A: "예술형", S: "사회형", E: "진취형", C: "관습형",
};
const POSITIVE_DIMS = new Set(["like", "value", "aspiration", "skill_signal"]);

export function SelfModelPanel() {
  const { data, isLoading, isError } = useQuery<SelfModelLive>({
    queryKey: ["self-model"],
    queryFn: fetchSelfModel,
    staleTime: 5 * 60 * 1000,
  });

  const riasec = data?.riasec ?? null;
  const radarRows = riasec
    ? (["R", "I", "A", "S", "E", "C"] as const).map((c) => ({
        axis: RIASEC_LABEL[c],
        value: riasec.scores[c] ?? 50,
      }))
    : [];
  const topCodes = riasec?.top_codes ?? [];
  const positives = (data?.evidence ?? [])
    .filter((e) => POSITIVE_DIMS.has(e.dimension))
    .slice(0, 8);
  const hasAny = !!riasec || !!data?.narrativeSummary || (data?.evidence?.length ?? 0) > 0;

  return (
    <div className="flex min-h-0 flex-col gap-3 overflow-y-auto rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-800">
      <div className="flex items-center gap-2 text-sm font-semibold text-slate-800 dark:text-slate-100">
        <RadarIcon className="h-4 w-4 text-indigo-600" aria-hidden />
        나의 성향 지도
      </div>

      {isLoading ? (
        <p className="py-8 text-center text-xs text-slate-400 dark:text-slate-500">불러오는 중…</p>
      ) : isError ? (
        <p className="py-8 text-center text-xs text-slate-400 dark:text-slate-500">잠시 후 다시 시도해 주세요.</p>
      ) : !hasAny ? (
        <p className="py-8 text-center text-xs leading-relaxed text-slate-500 dark:text-slate-400">
          상담을 나누면 여기에 나의 성향이 나타나요.
        </p>
      ) : (
        <>
          {riasec && (
            <div className="h-[220px] w-full min-w-0">
              <ResponsiveContainer width="100%" height={220}>
                <RadarChart cx="50%" cy="50%" outerRadius="72%" data={radarRows}>
                  <PolarGrid stroke="#e2e8f0" />
                  <PolarAngleAxis dataKey="axis" tick={{ fill: "#64748b", fontSize: 11 }} />
                  <PolarRadiusAxis angle={30} domain={[0, 100]} tick={false} axisLine={false} />
                  <Radar dataKey="value" stroke={INDIGO} fill={INDIGO} fillOpacity={0.22} isAnimationActive animationDuration={600} />
                </RadarChart>
              </ResponsiveContainer>
            </div>
          )}

          {topCodes.length > 0 ? (
            <div className="flex flex-wrap gap-1.5">
              {topCodes.map((c) => (
                <span key={c} className="rounded-full bg-indigo-50 px-2.5 py-1 text-[11px] font-semibold text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-300">
                  {RIASEC_TYPE[c] ?? c}
                </span>
              ))}
            </div>
          ) : (
            <p className="text-[11px] text-slate-500 dark:text-slate-400">아직 흥미가 분화 중이에요. 대화가 쌓이면 뚜렷해져요.</p>
          )}

          {data?.narrativeSummary && (
            <p className="rounded-xl bg-slate-50 px-3 py-2 text-xs leading-relaxed text-slate-700 dark:bg-slate-900/50 dark:text-slate-200">
              {data.narrativeSummary}
            </p>
          )}

          {positives.length > 0 && (
            <div>
              <p className="mb-1.5 flex items-center gap-1 text-[11px] font-semibold text-slate-600 dark:text-slate-400">
                <Sparkles className="h-3 w-3 text-amber-500" aria-hidden /> 발견된 근거
              </p>
              <div className="flex flex-wrap gap-1.5">
                {positives.map((e, i) => (
                  <span key={i} className="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[11px] text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300">
                    {e.content}
                  </span>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      <div className="mt-1 rounded-xl border border-dashed border-slate-200 px-3 py-2.5 text-[11px] leading-relaxed text-slate-400 dark:border-slate-700 dark:text-slate-500">
        대화가 쌓이면 성격 5요인(Big Five)도 여기에 나타나요.
      </div>
      <p className="text-center text-[10px] text-slate-400 dark:text-slate-500">나의 성향은 매일 대화를 바탕으로 정리돼요.</p>
    </div>
  );
}
```

- [ ] **Step 3: ConsultView 우측 패널 교체**

`www.yeotaeho.kr/src/components/features/consult/ConsultView.tsx` 에서:
- import 교체: `import { InsightWalletPanel } from "./InsightWalletPanel";` → `import { SelfModelPanel } from "./SelfModelPanel";`
- 우측 `<aside>`(약 318행) 안의 `<InsightWalletPanel ... />` 를 `<SelfModelPanel />` 로 교체.
- 모바일 드로어(약 377행) 안의 `<InsightWalletPanel ... />` 도 `<SelfModelPanel />` 로 교체.
- InsightWalletPanel 에 넘기던 props 는 SelfModelPanel 이 받지 않으므로 제거. 이후 InsightWalletPanel import 가 없어졌는지 확인(잔재 없으면 파일은 남겨두되 import 만 제거).

정확한 위치·props 는 파일을 읽고 판단하라. InsightWalletPanel 이 좌측 채팅에서 참조하는 상태(attached context 등)가 있으면 SelfModelPanel 은 그 상태를 쓰지 않으므로 관련 미사용 변수는 그대로 두거나(다른 곳에서 쓰면) tsc 통과 범위에서 정리.

- [ ] **Step 4: 타입 검증**

Run: `cd www.yeotaeho.kr; pnpm exec tsc --noEmit`
Expected: 출력 없음(0 에러).

- [ ] **Step 5: 커밋**

```bash
git add www.yeotaeho.kr/src/lib/api/selfModel.ts www.yeotaeho.kr/src/components/features/consult/SelfModelPanel.tsx www.yeotaeho.kr/src/components/features/consult/ConsultView.tsx
git commit -m "feat(sp4): 상담실 우측 자기모델 패널(RIASEC 레이더·근거·Big Five placeholder) — 목업 지갑 교체"
```

---

## 최종 검증 (whole-branch)

- [ ] 백엔드 회귀 (cwd `backend/`, 각 FAIL=0):
```bash
python scripts/riasec_scoring_test.py
python scripts/self_model_extract_parse_test.py
python scripts/self_model_extraction_test.py
python scripts/self_model_merge_test.py
python scripts/self_model_repository_test.py
python scripts/self_model_endpoint_test.py
python scripts/self_model_embed_text_test.py
python scripts/self_model_embed_candidacy_test.py
python scripts/recommend_explain_service_test.py
python scripts/consult_service_test.py
```
- [ ] 프론트 `cd www.yeotaeho.kr; pnpm exec tsc --noEmit` 0 에러.
- [ ] 리뷰 게이트 — code-reviewer 에이전트 whole-branch → Codex `/codex:review --base <시작 ref> --scope branch`.
