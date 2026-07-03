# SP-4 — 자기모델 RIASEC 점수화 + 상담실 시각화 설계

2026-07-03 확정. `/consult`(AI 상담실) 우측을 자기모델 실데이터로 시각화한다. 그 전제로, 코치가 top_codes만
내던 RIASEC 추출을 **6축 0~100 점수**로 바꾸고 대화가 쌓일수록 안정화(confidence 가중 블렌딩 + shrinkage)한다.
근거는 조사 문서 `backend/docs/research/2026-07-03-riasec-scoring-research.md`(워크넷·커리어넷·O*NET 채점 방식).

## 배경·근거 (조사 요약)

- 정식 RIASEC 검사(워크넷 직업선호도검사 S/L형, O*NET Interest Profiler)는 **6축을 독립 문항 풀로 단순 합산**해
  축별 원점수를 내고, top-2 코드는 그 순위에서 파생한다. → **per-axis 0~100 점수 저장이 정당**하다.
- 문항(관측치)이 적을수록 신뢰도가 낮다(O*NET Long α.93~.97 vs Mini α.70~.81). LLM 성격추정 선례
  (arXiv:2602.15848)도 "근거 부족 시 confidence 낮추고 50~70 중립으로 보수 채점"을 명시. → **shrinkage 필요**.
- 행동·서사 근거를 명시적 자기규정보다 높게 가중. 인접 축 상관(.3~.45)은 정상.

## 확정 결정 (사용자 확답)

| 결정 | 선택 |
|---|---|
| RIASEC 시각화 | 6축 레이더 — **top_codes가 아닌 실제 per-axis 점수** 기반(조사로 점수화 정당성 확인) |
| 점수 누적 | **confidence 가중 블렌딩 + shrinkage**(50 중립 방향, 근거 얇을 때) |
| 우측 패널 | 목업 `InsightWalletPanel` → 실데이터 `SelfModelPanel` **교체** |
| big_five | 현재 미수집(null) → **placeholder**(추출 방식은 후속 논의) |

## A. 저장 스키마 (`user_self_model.riasec` JSONB — DDL 불필요, 형태만 변경)

```json
{
  "scores":  {"R":0-100,"I":0-100,"A":0-100,"S":0-100,"E":0-100,"C":0-100},
  "raw":     {"R":0-100, ...},
  "weights": {"R":float, ...},
  "top_codes": ["I","A"]
}
```

- `raw`·`weights` — shrink 전 축별 confidence-가중 누적 평균과 누적 가중치(다음 블렌딩 입력).
- `scores` — `raw`에 shrinkage 적용한 표시용(레이더가 읽음).
- `top_codes` — `scores` 순위에서 파생(주코드). 임계 미달이면 부분/빈.
- **하위호환**: 기존 행은 `{"top_codes":[...]}`만 → `raw`/`weights` 없음을 "중립 50·weight 0"으로 취급해
  다음 추출 때 실점수화. SP-3 임베딩은 `riasec.top_codes`를 계속 읽으므로 무영향.

## B. 추출 → 점수화

### B-1. LLM 프롬프트·파서 (`core/llm/client.py`)

- `_SELF_MODEL_EXTRACT_SYSTEM_PROMPT` 개정: RIASEC를 **6축 각각 0~100 점수 + 축별 confidence(0~1)** 로 채점.
  주입 원칙 — (1) 행동·서사 근거를 명시적 자기규정보다 높게 가중, (2) 근거 얇은 축은 50 방향 보수 채점·낮은
  confidence, (3) top_codes 별도 추정 금지(서버가 점수에서 파생). 서사·evidence 부분은 기존 유지.
- 출력 형식 변경: `riasec_top_codes`·`riasec_confidence` 제거 → `riasec_scores: {6키}`,
  `riasec_axis_confidence: {6키}` 추가.
- `_parse_self_model_extract` — `riasec_scores`·`riasec_axis_confidence`를 6키 검증·0~100/0~1 클램프,
  누락 키는 score 50·conf 0. 반환 dict 키를 `riasec_scores`·`riasec_axis_confidence`로. narrative·evidence 파싱 불변.

### B-2. 순수 블렌딩 (`self_model_service.py` 또는 신규 `riasec_scoring.py`)

`blend_riasec(existing_riasec: dict | None, window_scores: dict, window_conf: dict) -> dict`:

- 축별 confidence-가중 증분 평균 — 기존 `raw[a]`(없으면 50)·`weights[a]`(없으면 0)에 대해
  `W' = W + conf_w[a]`, `raw' = (raw*W + score_w[a]*conf_w[a]) / W'`(W'=0이면 raw'=50).
- shrinkage(표시·코드용) — `SHRINK_K = 4`; `display[a] = 50 + (raw'[a]-50) * min(1, W'[a]/SHRINK_K)`, 반올림 정수.
- `top_codes` — `TOP_MIN = 55`; display 상위 2축 중 `display>TOP_MIN` 인 것만(0~2개). 없으면 빈 배열("분화 중").
- 반환 `{scores: display, raw, weights, top_codes}`. 순수·결정론.

### B-3. 병합 연결

- `self_model_extraction_service.extract_session` — `incoming.riasec = {"window_scores": result["riasec_scores"],
  "window_conf": result["riasec_axis_confidence"]}`(항상 non-null, 6축 채점이 기본). `axis_confidence.riasec`은
  6축 confidence 평균으로 설정.
- `merge_structured`(`self_model_service.py`) — riasec 축 처리: `incoming.riasec`에 `window_scores`가 있으면
  overwrite 대신 `blend_riasec(existing.riasec, window_scores, window_conf)` 결과를 저장. `source == user_form`
  이면(향후 수동 입력) 기존 overwrite 규칙 유지. narrative·big_five 축 로직은 불변.
- SP-3 임베딩·설명은 `riasec.top_codes`만 읽으므로 계약 유지.

## C. 프론트 (지갑 교체)

- 신규 `www.yeotaeho.kr/src/lib/api/selfModel.ts` — `getSelfModel()` → 타입 `SelfModelLive`
  `{riasec: {scores, top_codes} | null, bigFive: null, narrativeSummary, axisConfidence, evidence: [...]}`.
  `GET /api/user/self-model`, `data.selfModel` 반환.
- 신규 `www.yeotaeho.kr/src/components/features/consult/SelfModelPanel.tsx`:
  1. **RIASEC 6축 레이더** — recharts `RadarChart`(기존 의존성), 축 라벨 한국어(현실·탐구·예술·사회·진취·관습),
     값 `riasec.scores`. 데이터 없으면 빈 상태.
  2. **주요 유형 배지** — `top_codes`를 한국어 유형명으로. 없으면 "아직 흥미가 분화 중" 문구.
  3. **서사 한 줄** — `narrativeSummary`(있을 때).
  4. **발견된 근거 칩** — `evidence` 중 긍정(dimension like/value/aspiration/skill_signal) content 칩.
  5. **big_five placeholder** — "대화가 쌓이면 성격 5요인도 나타나요."(카드).
  6. **신뢰도 캡션** — RIASEC axisConfidence 또는 top_codes 유무로 "매일 대화가 정리돼요"·"분화 중" 안내.
  7. **빈 상태**(자기모델 없음) — 격려 문구("상담을 나누면 여기에 나의 성향이 나타나요.").
- `ConsultView.tsx` — 우측 `<aside>`(및 모바일 드로어)의 `InsightWalletPanel`을 `SelfModelPanel`로 교체.
  자기모델은 로그인 필요 → 미로그인/빈 데이터는 빈 상태 처리. TanStack Query로 mount 시 fetch.
- 갱신 시점: 자기모델은 일별 추출 반영 — 패널 캡션으로 명시. 실시간 재추출은 범위 밖.

## D. 테스트

- 백엔드 순수: `blend_riasec` — (a) 첫 관측(weight 0→window), (b) 반복 관측 confidence 가중 평균 수렴,
  (c) shrinkage(근거 1건 near-50, 근거 많으면 완전 표현), (d) top_codes 파생(55 임계·상위2), (e) 하위호환
  (top_codes만 있는 existing). 파서 — 6축 scores/conf 검증·클램프·누락 키 기본값.
- 백엔드 통합: 추출 2회 누적 시 scores 안정화·top_codes 갱신(FakeLLM, Neon). SP-2b 추출 테스트를 새 형태로 갱신.
- 프론트: `pnpm exec tsc --noEmit` 0 에러.

## E. 범위 밖 (후속)

- **Big Five 추출**(사용자 요청 후속 논의) — 동일 blend+shrinkage 방법론을 5요인에 적용. big_five placeholder를 실데이터로.
- 실시간 재추출(현재 일별). 자기모델 편집·삭제권(프라이버시). 레이더에 규준집단 백분위(현재 절대 점수).

## 파일 지도

| 영역 | 파일 |
|---|---|
| LLM·파서 | `backend/core/llm/client.py` |
| 블렌딩·병합 | `backend/domain/user_intelligence/hub/services/self_model_service.py` (+선택 `riasec_scoring.py`) |
| 추출 연결 | `backend/domain/user_intelligence/hub/services/self_model_extraction_service.py` |
| 프론트 | `www.yeotaeho.kr/src/lib/api/selfModel.ts` · `src/components/features/consult/SelfModelPanel.tsx` · `ConsultView.tsx` |
