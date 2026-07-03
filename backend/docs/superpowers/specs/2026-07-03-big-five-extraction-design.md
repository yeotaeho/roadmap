# SP-5 — Big Five 성격 5요인 추출·시각화 설계

2026-07-03 확정. RIASEC(SP-4)에서 세운 방법론(6축 독립 채점 → confidence 가중 블렌딩 → shrinkage)을
Big Five 5요인(OCEAN)에 적용한다. 상담 대화에서 성격 특질을 추정해 `user_self_model.big_five`를 채우고,
`/consult` 우측 패널에 5개 막대로 시각화한다.

## 확정 결정 (사용자 확답)

| 결정 | 선택 |
|---|---|
| 척도 | 5요인 각 **0~100 단일 축**, 50 = 중립/파악 중(RIASEC 인프라 재사용). UI는 "낮음" 대신 "중간·파악 중" |
| 민감성(신경성) | **정서안정성(100−N)** 으로 뒤집어 강점 프레이밍. 부정 단정 금지. 민감 근거는 기존대로 격리 |
| 추출 | RIASEC과 **동일 LLM 호출**에서 5축 동시 채점 + **더 강한 shrinkage(K=8)** |
| 저장 형태 | **canonical OCEAN 저장**(N 원값), flip은 **표시층에서만** |
| 시각화 | **5개 가로 막대**(개방·성실·외향·우호·정서안정) |

## 배경

- Big Five는 RIASEC(흥미·단극)과 달리 **양극 성격 특질**이고 일부(특히 신경성)는 민감하다. 그래서 척도 의미
  (50=중립·"저"가 아니라 "파악 중")·민감성 처리(안정성 뒤집기)가 새 논점이다.
- 짧은 대화에서 성격은 흥미보다 추정 신뢰도가 낮다 — shrinkage를 RIASEC보다 강하게(K 4→8) 건다.
- `user_self_model.big_five` 컬럼은 SP-1부터 존재하나 현재 항상 null(추출 미구현).

## A. 저장 스키마 (`user_self_model.big_five` JSONB — DDL 불필요)

RIASEC와 동형:
```json
{ "scores":  {"O":0-100,"C":0-100,"E":0-100,"A":0-100,"N":0-100},
  "raw":     {"O":0-100, ...},
  "weights": {"O":float, ...} }
```
- 코드: `O` 개방성 · `C` 성실성 · `E` 외향성 · `A` 우호성 · `N` **신경성(canonical, 높을수록 신경성 高)**.
- `top_codes` 없음(Big Five는 코드 개념이 없고 막대로 표시).
- **N은 canonical 원값 저장** — "정서안정성 = 100−N" 변환은 오직 프론트 표시층에서.
- 기존 null 행은 blend가 중립 50·weight 0으로 취급(하위호환).

## B. 블렌딩 일반화 (`riasec_scoring.py` 리팩터)

SP-4 `blend_riasec`의 핵심을 축-집합 일반 함수로 추출한다.

- `blend_axes(existing_scores: dict|None, window_scores, window_conf, codes: tuple, shrink_k: float) -> {"scores": {int}, "raw": {float}, "weights": {float}}` — 축별 confidence 가중 증분 평균 + shrinkage(`50+(raw-50)·min(1,W/shrink_k)`). SP-4 blend 수식 그대로, 축 집합만 파라미터화.
- `blend_riasec(existing, ws, wc)` = `blend_axes(..., RIASEC_CODES, SHRINK_K=4)` 위에 `top_codes` 파생(기존 계약 유지 — SP-3 임베딩·설명이 읽음).
- 신규 `blend_big_five(existing, ws, wc)` = `blend_axes(..., BIGFIVE_CODES, BIGFIVE_SHRINK_K=8)`. top_codes 없음.
- 상수: `BIGFIVE_CODES = ("O","C","E","A","N")`, `BIGFIVE_SHRINK_K = 8`.
- `blend_axes`는 `existing`에서 `raw`/`weights`를 안전 추출(옛/누락 형태는 50·0) — SP-4 `_axis` 재사용.

## C. 추출 — 같은 호출에 5축 추가

### C-1. 프롬프트·파서 (`core/llm/client.py`)

- `_SELF_MODEL_EXTRACT_SYSTEM_PROMPT` 확장: RIASEC 6축과 **함께** Big Five 5축(O·C·E·A·N)을 각 0~100 + 축별
  confidence로 채점. 원칙 — (1) **N은 canonical**(높을수록 정서적으로 예민·반응적)로 채점하되 **병리 단정 금지**,
  (2) 행동·서사 근거를 명시적 자기규정보다 높게 가중, (3) 근거 얇은 축은 50 보수·낮은 confidence.
  RIASEC·narrative·evidence 부분은 SP-4 그대로.
- 출력 추가: `big_five_scores: {O,C,E,A,N}`, `big_five_axis_confidence: {O,C,E,A,N}`.
- `_parse_self_model_extract` — `big_five_scores`·`big_five_axis_confidence`를 5키 검증·0~100/0~1 클램프
  (누락 키 score 50·conf 0). 반환 dict에 두 키 추가. RIASEC·narrative·evidence 파싱 불변.

### C-2. 추출 서비스 (`self_model_extraction_service.py`)

`extract_session`에서 incoming.big_five를 채운다(기존 None).
```python
        bf_conf = result["big_five_axis_confidence"]
        incoming = {
            "riasec": {"window_scores": result["riasec_scores"], "window_conf": result["riasec_axis_confidence"]},
            "big_five": {"window_scores": result["big_five_scores"], "window_conf": bf_conf},
            "narrative_summary": result["narrative"],
            "axis_confidence": {
                "riasec": ...(기존 riasec 평균),
                "big_five": sum(bf_conf.values()) / len(bf_conf) if bf_conf else 0.0,
                ...(narrative)
            },
        }
```

### C-3. 병합 (`self_model_service.py`)

`merge_structured`의 riasec 블렌드 분기를 `axis in ("riasec", "big_five")`로 일반화하고 축별 blend 함수를 분기.
```python
        if axis in ("riasec", "big_five") and isinstance(inc, dict) and "window_scores" in inc:
            if source != SOURCE_USER_FORM:
                if existing_source == SOURCE_USER_FORM and base.get(axis) is not None:
                    continue  # user_form 우위 — blend 잠식 안 함
                existing_axis = base.get(axis) if isinstance(base.get(axis), dict) else None
                blender = blend_riasec if axis == "riasec" else blend_big_five
                result[axis] = blender(existing_axis, inc["window_scores"], inc["window_conf"])
                merged_conf[axis] = sum(inc["window_conf"].values()) / len(inc["window_conf"]) if inc["window_conf"] else 0.0
                continue
```
narrative·기타 축 로직 불변. user_form 보존 가드는 두 축 모두에 동일 적용.

## D. 서빙 + 프론트 (flip은 표시층)

- `get_self_model`은 이미 `bigFive = model["big_five"]`를 그대로 서빙 — 변경 없음.
- `www.yeotaeho.kr/src/lib/api/selfModel.ts` — `bigFive` 타입을 `{ scores: { O:number;C:number;E:number;A:number;N:number } } | null` 로.
- `SelfModelPanel.tsx` — Big Five placeholder 카드를 **5개 가로 막대**로 교체.
  - 라벨·값: 개방성=`O` · 성실성=`C` · 외향성=`E` · 우호성=`A` · **정서안정성=`100 − N`**(flip은 여기서만).
  - 각 막대 0~100, 50 기준선 표시. 근거 얇을 때는 "파악 중" 톤(중립).
  - `bigFive` null 또는 `scores` 없으면 기존 placeholder 문구 유지("대화가 쌓이면 성격 5요인이 나타나요.").
  - **부정 단정 금지**: 높은 N도 "정서안정성 낮음"으로 라벨링하지 않고 낮은 안정성 막대 + 중립 톤. 병리 표현 없음.

## E. 테스트

- 백엔드 순수: `blend_big_five`(=blend_axes) — 첫 관측·반복 누적 수렴·K=8 shrinkage(RIASEC K=4보다 완만한 표현)·
  5축·하위호환(null existing). `blend_riasec` 회귀(래퍼 유지·top_codes 파생 불변). 파서 — big_five 5축 클램프·누락 기본값.
- 백엔드 통합: 추출 2회 누적 시 big_five scores 안정화(FakeLLM, Neon). SP-4 추출 테스트를 big_five 포함 형태로 갱신.
- 프론트 `pnpm exec tsc --noEmit` 0 에러.

## F. 범위 밖 (후속)

- **Big Five를 임베딩·추천 신호로 사용** — 현재 임베딩·추천은 `riasec.top_codes`만 읽는다. Big Five를 사용자 임베딩
  텍스트나 매칭 신호에 넣는 것은 별도 SP(신호 매핑·검증 필요).
- **규준집단 백분위** — 정식 검사는 규준집단 대비 백분위를 제공하나, 검증된 규준 데이터가 없어 유효 산출 불가.
  현재는 절대 0~100 점수만. 규준 확보 시 후속.
- 실시간 재추출(현재 일별). big_five 신뢰도 캡션 실데이터화.

## 파일 지도

| 영역 | 파일 |
|---|---|
| 블렌딩 | `backend/domain/user_intelligence/hub/services/riasec_scoring.py`(`blend_axes`·`blend_big_five`·상수) |
| LLM·파서 | `backend/core/llm/client.py` |
| 추출·병합 | `backend/domain/user_intelligence/hub/services/self_model_extraction_service.py` · `self_model_service.py` |
| 프론트 | `www.yeotaeho.kr/src/lib/api/selfModel.ts` · `src/components/features/consult/SelfModelPanel.tsx` |
