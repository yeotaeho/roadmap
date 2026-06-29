# 시장 전망 수직 — TimesFM 14일 예측 설계 (Design Spec)

작성일 2026-06-30 · 도메인 `market_insight` · 상태 **설계 승인 대기**

---

## 1. 개요·목표

현재 Pulse 점수는 "과거~현재의 열기(활동량) + 방향(감성·시장 등락)"을 측정한다. 등락 modifier마저 **전일 종가 대비(과거)** 신호다. 제품의 핵심 컨셉인 "선행 행동 지표"를 강화하려면 **미래를 가리키는** 지표가 필요하다.

**목표** — Google TimesFM(시계열 파운데이션 모델)로 섹터별 시장 자금 흐름의 **향후 14일 추세를 예측**해, Pulse와 나란히 서빙하는 독립 '시장 전망' 수직을 추가한다. Pulse 점수 산출은 건드리지 않는다.

**비목표** — Pulse 점수 자체 예측(일별 Gold 누적 후 별도 과제), 다변량 예측, 실시간 온디맨드 추론.

---

## 2. 브레인스토밍 결론 (확정 결정)

| 결정 | 선택 | 비고 |
|---|---|---|
| 예측의 용도 | **독립 '시장 전망' 수직** | Pulse 점수 불변·비파괴 |
| 산출물 형태 | **전망 점수(0~100) + 방향 배지** | Pulse와 동일 형태 → 프론트 UI 재사용 |
| 예측 기간(horizon) | **14일** | 정확도·선행성 균형 |
| 구현 접근 | **티커별 예측 → % 수익률 → turnover 가중 섹터 집계 → 0~100** | 실 시계열 충실·통화 중립 |
| 실행 | **스케줄러 배치**, API는 Gold만 읽음 | 모델을 요청 경로에 두지 않음 |

---

## 3. Phase 0 실현가능성 검증 결과 (통과)

Python 3.13.5 / torch313(torch 2.9.1+cu130)에서 end-to-end 스모크 완료.

- **설치** — `pip install timesfm[torch]==2.0.1`. 신규 패키지 5개(timesfm + CLI 헬퍼)뿐, **JAX 불필요·torch 재설치 없음·충돌 없음**. `requires-python >=3.10`(3.13 포함).
- **모델** — PyPI 패키지(2.0.1)가 실제로 담은 건 **TimesFM 2.5**(`TimesFM_2p5_200M_torch`). 문서의 구 `timesfm.TimesFm(hparams=…, checkpoint=…)` API는 폐기.
- **API 시그니처(확정)**:
  ```python
  model = timesfm.TimesFM_2p5_200M_torch.from_pretrained("google/timesfm-2.5-200m-pytorch")
  model.compile(timesfm.ForecastConfig(
      max_context=512, max_horizon=64,
      normalize_inputs=True,
      use_continuous_quantile_head=True,
      fix_quantile_crossing=True,
  ))
  point, quantile = model.forecast(horizon=14, inputs=[np.ndarray, ...])
  # point: (N, 14)  ·  quantile: (N, 14, 10)
  ```
- **성능** — 로드 84s(최초 1회, `~/.cache/huggingface/hub`에 캐시), 추론 **0.6s**. `inputs`가 리스트라 ~30개 티커를 **단일 forecast 호출로 배치** 가능.
- **신뢰도** — 스텝당 10분위수 제공 → 밴드폭으로 confidence 산출.
- **운영 경고(무해)** — Windows symlink 경고·`hf_xet` 미설치 폴백. `HF_HUB_DISABLE_SYMLINKS_WARNING`·`hf_xet`로 정리 선택 가능.

→ 폴백(Chronos·별도 워커) 불필요. 본 설계 그대로 유효.

---

## 4. 아키텍처·도메인 배치 (Hub-Spoke)

무거운 모델(spoke/infra)과 순수 산출 로직(hub/services)을 **분리**한다. Pulse가 `pulse_pipeline`(순수)과 LLM client를 분리한 것과 동일 철학으로, 핵심 수학은 torch 없이 단위 테스트된다.

```
domain/market_insight/
├── spokes/infra/timesfm_forecaster.py      # 모델 래퍼(체크포인트 로드·추론) + Forecaster Protocol
├── hub/services/forecast_pipeline.py        # 순수: 수익률→점수, turnover 가중 집계, 배지·신뢰도
├── hub/services/forecast_refine_service.py  # 오케스트레이션(조회→예측→파이프라인→멱등 replace)
├── hub/repositories/forecast_repository.py  # 티커 시계열 조회·Silver/Gold replace·서빙
├── models/bases/refined_market_forecast_silver.py
├── models/bases/market_forecast_log.py
└── models/transfer/forecast_dto.py          # Pydantic 응답 DTO
```

**Forecaster Protocol** — `forecast_pipeline`·`forecast_refine_service`는 추상 인터페이스에만 의존한다. 테스트는 결정론적 fake forecaster를 주입해 모델·네트워크 없이 검증한다.

```python
class Forecaster(Protocol):
    def forecast_returns(
        self, series_by_ticker: dict[str, list[float]], horizon: int
    ) -> dict[str, ForecastPoint]: ...
# ForecastPoint = (predicted_return_pct: float, band_rel: float)  # band_rel = 분위수 상대 밴드폭
```

---

## 5. 데이터 흐름

```
raw_market_timeseries (티커×거래일 close_price·turnover, ~250거래일)
   │  forecast_repository.fetch_ticker_series()
   ▼
{ticker: [close_price...]}  +  {ticker: 상대 turnover 가중}
   │  TimesfmForecaster.forecast_returns(series, horizon=14)   ← 단일 배치 호출
   ▼
{ticker: (predicted_return_pct, band_rel)}
   │  forecast_pipeline.compute_forecast(...)
   │    · 티커 → 섹터 매핑(_MARKET_SOURCE_MAP 재사용, 광범위지수 제외)
   │    · turnover 가중 평균 → 섹터 예측 수익률·신뢰도
   │    · 0~100 전망 점수 + 방향 배지
   ▼
refined_market_forecast_silver  (멱등 replace by reference_date+horizon)
   │  project_to_gold
   ▼
market_forecast_log  (Gold)
   │  GET /api/insight/forecast  (섹터별 최신 1행 + sectors 조인)
   ▼
프론트 — Pulse와 동일 speedometer UI 재사용
```

---

## 6. 스키마 (Pulse 패턴 미러)

### Silver `refined_market_forecast_silver`

| 컬럼 | 타입 | 설명 |
|---|---|---|
| id | BigInteger PK | |
| sector_slug | String(50) FK→sectors.slug | |
| reference_date | Date | 예측 기준일(최신 거래일) |
| horizon_days | Integer | 14 (거래일 스텝 수) |
| target_date | Date | 정보용 라벨 — reference_date의 영업일 +horizon 근사(비load-bearing) |
| predicted_return_pct | Numeric(8,4) | 섹터 예측 14스텝 수익률(%) |
| forecast_score | Integer | 0~100 (CheckConstraint) |
| direction_badge | String(20) | 강세/상승/중립/하락/약세 전망 |
| confidence | Numeric(3,2) | 0~1 (분위수 밴드 기반) |
| ticker_count | Integer | 집계에 쓰인 티커 수 |
| model_name | String(120) | `timesfm-2.5-200m` |
| processed_at | DateTime(tz) | server_default now |

자연키 유니크 `(sector_slug, reference_date, horizon_days)`. 인덱스 `(sector_slug, reference_date DESC)`.

### Gold `market_forecast_log`

| 컬럼 | 타입 | 설명 |
|---|---|---|
| id | BigInteger PK | |
| sector_slug | String(50) FK | |
| forecast_date | Date | = Silver reference_date |
| horizon_days | Integer | 14 |
| target_date | Date | |
| score | Integer | 0~100 (CheckConstraint) |
| direction_badge | String(20) | |
| predicted_return_pct | Numeric(8,4) | |
| confidence | Numeric(3,2) | |
| created_at | DateTime(tz) | server_default now |

자연키 유니크 `(sector_slug, forecast_date, horizon_days)`. 인덱스 `(forecast_date, sector_slug)`.

---

## 7. 산출 로직 (순수 함수·설정값화)

**책임 경계** — 1)은 모델 래퍼(`timesfm_forecaster`)가 자신의 입력 시계열·예측 출력으로 산출해 `(predicted_return_pct, band_rel)`을 반환한다. 2)~5)는 순수 파이프라인(`forecast_pipeline`)이 래퍼 출력 + 리포지토리가 준 turnover 가중으로 수행한다. 덕분에 파이프라인 테스트는 모델·분위수 배열에 의존하지 않는다.

```
# 1) [래퍼] 티커 14스텝(거래일) 예측 → % 수익률
predicted_return_pct(ticker) = (point[마지막 스텝] − last_close) / last_close × 100

# 2) [파이프라인] 섹터 집계 (통화 중립: 수익률은 무단위 / 가중치는 상대 turnover)
rel_turnover(ticker) = 최신 거래일 turnover ÷ 그 티커의 기간 평균 turnover   # 통화 중립화
sector_return = Σ(predicted_return_pct × rel_turnover) / Σ rel_turnover

# 3) 점수
forecast_score = clamp(round(50 + K_f × sector_return), 0, 100)         # K_f 기본 5.0

# 4) 방향 배지 (sector_return 임계값)
≥ +up_strong(5.0) → 강세 전망 · ≥ +up(1.5) → 상승 전망
> −up(1.5)       → 중립 전망 · > −up_strong(5.0) → 하락 전망 · else 약세 전망

# 5) 신뢰도 (분위수 밴드폭, 좁을수록 높음)
band_rel = (q_hi − q_lo) at 마지막 스텝, |point| 정규화                  # [래퍼가 band_rel 산출]
confidence = clamp(1 − band_rel / band_norm, 0, 1)                      # band_norm 기본 0.3
```

> 분위수 10개의 레벨 인덱스(예: 0.1~0.9 deciles)는 구현 시 래퍼가 실제 배열을 확인해 확정·문서화한다. 신뢰도는 대표 내부 밴드(q90−q10 근사)를 쓴다. 파이프라인은 이미 계산된 `band_rel`만 받는다.

---

## 8. 모델 래퍼 (`spokes/infra/timesfm_forecaster.py`)

- **lazy 싱글톤** — import 시점이 아니라 첫 `forecast_returns` 호출에서 `from_pretrained`+`compile`(openai lazy import 패턴과 동일). `timesfm` 미설치·로드 실패 시 명시적 예외.
- **배치** — 모든 티커 시계열을 한 번의 `model.forecast(horizon, inputs=[...])`로 추론. 입력 순서↔출력 행 매핑 보존.
- **메모리** — 배치 잡 1회 로드 후 잡 종료 시 해제(영구 상주 회피). `model_name = "timesfm-2.5-200m"` 기록.
- **min_history 게이트** — `< forecast_min_history`(기본 64) 시계열 티커는 제외(섹터 집계에서 빠짐).
- **가드** — NaN/inf 예측·0 분모(last_close=0) 방어.

---

## 9. 컴포넌트 (신규/수정)

**신규**
- `models/bases/refined_market_forecast_silver.py` · `models/bases/market_forecast_log.py` (ORM)
- `spokes/infra/timesfm_forecaster.py` (모델 래퍼 + Protocol)
- `hub/services/forecast_pipeline.py` (순수 산출)
- `hub/services/forecast_refine_service.py` (오케스트레이션)
- `hub/repositories/forecast_repository.py` (조회·replace·서빙)
- `models/transfer/forecast_dto.py` (응답 DTO)
- `alembic/versions/<hash>_add_market_forecast_tables.py` (수동 작성)
- `scripts/market_forecast_test.py` (순수 단위·fake forecaster)
- `scripts/market_forecast_refine.py` (수동/cron 배치 엔트리)

**수정**
- `api/v1/insight/insight_routor.py` — `GET /api/insight/forecast` (+ 선택 `POST /forecast/refine`)
- `core/scheduler.py` — `_job_market_forecast`(일별, 시장 수집 후)
- `core/config/settings.py` — `FORECAST_*` 필드
- `alembic/env.py` — 신규 ORM 모델 등록(autogenerate DROP 방지)
- `requirements.txt` — `timesfm[torch]==2.0.1` 핀 추가

`main.py`는 insight_router에 이미 포함돼 변경 없음.

---

## 10. 운영·스케줄러

- `_job_market_forecast` — 일별 1회, 시장 데이터 수집/Pulse refine 이후 순서. `timesfm` 미설치 시 skip+로그(키 없으면 skip하는 `_job_text_classify` 패턴과 동일).
- 멱등 — `(reference_date, horizon_days)`로 Silver/Gold replace. 같은 날 재실행 시 덮어씀.
- 수동 트리거 — `scripts/market_forecast_refine.py` 또는 `POST /forecast/refine`(관리자).

---

## 11. 에러 처리·엣지

- 티커 이력 부족(`< min_history`) → 제외.
- 섹터에 쓸 티커 0개 → **행 미생성**(날조 금지).
- 티커별 추론 실패 → 로그+스킵, 배치 계속.
- NaN/inf·0 분모 → 가드(해당 티커 제외).
- 데이터 staleness — 최신 거래일 기준으로 예측(별도 플래그 없음, 단순).

---

## 12. 설정값 (`FORECAST_*` env)

| 설정 | 기본 | 의미 |
|---|---|---|
| `forecast_horizon_days` | 14 | 예측 기간 |
| `forecast_score_k` | 5.0 | 수익률→점수 계수 |
| `forecast_up_threshold` | 1.5 | 상승/하락 배지 경계(%) |
| `forecast_up_strong_threshold` | 5.0 | 강세/약세 배지 경계(%) |
| `forecast_min_history` | 64 | 티커 최소 시계열 길이 |
| `forecast_band_norm` | 0.3 | 신뢰도 밴드 정규화(band_rel→confidence) |
| `forecast_model_repo` | `google/timesfm-2.5-200m-pytorch` | 체크포인트 |

Pulse `PULSE_*`와 동일하게 코드 변경 없이 `.env` 재조정.

---

## 13. 테스트 전략

- **순수 파이프라인**(`scripts/market_forecast_test.py`, torch 無·fake forecaster):
  - 수익률→점수 매핑·clamp
  - turnover 가중 섹터 집계 + **통화 중립**(USD+KRW 수익률 혼합이 합산돼도 정상)
  - 배지 임계값 경계
  - 신뢰도 밴드 산출
  - 빈/이력부족/0분모 처리(행 미생성)
- **마이그레이션** — 로컬 적용 후 두 테이블·제약·자연키 존재 확인.
- **E2E 스모크** — fake forecaster 주입 refine → `GET /api/insight/forecast` 섹터 점수 반환.
- **실모델 스모크(수동 게이트)** — Phase 0 스크립트 재사용(`scripts/market_forecast_refine.py --smoke`).

---

## 14. 후속 / 범위 밖

- Pulse 시장 modifier를 본 예측으로 격상(둘 다 안 → 차기).
- Pulse 점수 자체 시계열 예측(일별 Gold 누적 후).
- 별도 Py 워커/컨테이너로 모델 격리(prod 스케일 시, master MSA 분리 후보와 결).
- `hf_xet` 도입(다운로드 가속)·`forecast_band_norm` 실데이터 튜닝.
- XReg 공변량(이벤트·금리) 결합 예측.
