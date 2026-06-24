# Silver Pulse 전략·구현 — Bronze → 섹터 모멘텀

> 도메인: market_insight · 산출: Pulse 탭(섹터별 트렌드 점수)
> Silver `refined_pulse_metric_silver` → Gold `pulse_metrics_log` (마이그레이션 `f1a2b3c4d5e6`·`a1b2c3d4e5f6`)
> 최종 갱신: 2026-06-24 (첫 end-to-end 가동)

## 1. 목적 — 왜 Silver인가

Bronze는 "돈·기술·관심의 흐름" 원천을 모으지만, 그 자체로는 진로 인사이트가 아니다. **Silver가 이종 신호를 섹터 모멘텀으로 통약·정제**하고, **Gold는 그 단순 사영(projection)** 으로 UI에 서빙한다. Pulse는 가동된 첫 Silver다(ERD §5.3 흐름 실증).

```
raw_economic/innovation/people/market_timeseries (Bronze)
   └─(축별 집계 + 통약 정규화)→ fuse → compute_silver
        └─ refined_pulse_metric_silver (Silver, 섹터×일자 정규화 시계열)
              └─(사영)→ pulse_metrics_log (Gold) → GET /api/insight/pulse
```

## 2. 컴포넌트

| 파일 | 역할 |
|---|---|
| `hub/services/pulse_pipeline.py` | **순수함수**: `fuse_signals`·`compute_silver`(zscore/pct_change/ma_ratio)·`project_to_gold`. 결정론적·DB 무의존. |
| `hub/repositories/pulse_repository.py` | Bronze 4축 집계 SQL + 통약 정규화 + 멱등 `replace_silver/gold` + `fetch_latest_gold`(서빙). |
| `hub/services/pulse_refine_service.py` | 오케스트레이션 `refine_and_serve`(axis→fuse→silver→gold→commit). |
| `models/bases/{refined_pulse_metric_silver,pulse_metrics_log}.py` | ORM(env.py 등록 — autogenerate DROP 방지). |
| 라우터 `api/v1/insight/insight_routor.py` | `GET /api/insight/pulse`(서빙)·`POST /api/insight/pulse/refine`(수동 트리거). |
| 스케줄러 `_job_pulse_refine` | 일별 멱등 재생성. |

## 3. 4축 융합 설계

섹터(`sectors.slug` 12개)별 일자 신호를 4축에서 모은다.

| 축 | Bronze | 섹터 매핑 | 가중치 |
|---|---|---|---|
| innovation | raw_innovation_data(arXiv·GitHub·관세청·테크블로그) | `sector_source_map`(arxiv_category/github_topic/customs_group/tech_category) | 1.0 |
| economic | raw_economic_data(naver datalab 등) | `_SECTOR_CODE_MAP`(industry_sector/group_name 코드) | 1.0 |
| people | raw_people_data(HRDNET 훈련) | `_SECTOR_CODE_MAP`(sector_name) | 0.7 |
| **market(자본 흐름)** | raw_market_timeseries(Yahoo 16티커·1년) | `_MARKET_SOURCE_MAP`(source_type→sector) | 1.0 |

- **기준일**: 카운트축은 `COALESCE(published_at, collected_at)::date`(실 발생일로 분산 — 백필 한 점 쏠림 완화). 시장축은 `trade_date`.
- **섹터 무귀속 제외**: 신호유형 코드(CAPITAL_MARKET·STARTUP_VC 등)·광범위 지수(SPY·QQQ·ARKK)는 섹터 강제 매핑 = 날조이므로 skip.

## 4. 핵심 설계 — 이종 단위 통약(`_normalize_axes`)

**문제**: 시장 거래대금(수십억 KRW)이 혁신 카운트(1~50)를 융합에서 압도(`fuse_signals`는 raw 가중합).

**해법**: 각 축을 **축별 min-max 0~100 정규화** 후 융합. 시장 turnover와 논문 카운트가 동등 band가 된다. 모멘텀은 `compute_silver`의 윈도우 상대변화로 산출되므로, 정규화가 섹터의 *시간 변동(상대 추세)* 은 보존하면서 *축간 스케일 격차* 만 제거한다. 단일/동일값 축(span=0)은 50(중립).

### 시장축 통화 중립화(중요)
Yahoo는 **혼합 통화**(USD ETF + KRW 주식). raw SUM은 오류. 따라서 **티커별 상대유량**(당일 거래대금 ÷ 그 티커의 기간 평균, window function)으로 통화 중립화한 뒤 섹터로 합산한다(`_MARKET_AXIS_SQL`).

## 5. 모멘텀·배지 + 안전장치

- `compute_silver`: 섹터 시계열을 윈도우(기본 20일) 기준선 대비 정규화 → `normalized_score`(0~100)·`momentum_pct`·`status_badge`(태풍급/급상승/상승/보합/하락).
- **momentum 클램프**(`MOMENTUM_CAP=9999.99`): 희소 베이스라인이 만드는 수백만 % 노이즈 + NUMERIC(8,2) 오버플로 차단.
- **min_history 게이트**(운영 `refine_and_serve`에서 5): 직전 관측 5점 미만 섹터는 중립(보합) — 이력 부족 섹터의 거짓 급등(태풍급) 차단. (테스트 기본 0 → 기존 25 케이스 불변.)

## 6. 멱등성
`replace_silver`(baseline_method 단위 DELETE+INSERT)·`replace_gold`(전체 DELETE+INSERT). 재실행 시 Silver/Gold 동일(검증: 1,442행 2회 일치). Gold는 계산 없는 순수 사영, 읽기 전용 서빙.

## 7. 현재 산출 품질 — 정직한 평가

✅ **엔진 실증**: end-to-end 가동, 시장 5섹터(ai-data·semiconductor·bio-health·energy-climate·food-agri)는 **1년 실시계열로 합리적 모멘텀**(예: semiconductor 일별 -18%~+49%).

⚠️ **데이터 성숙도 한계(코드 아님)**:
- 카운트축(혁신·경제·사람)은 **일회성 백필이라 실 일별 시계열이 없음** → 시장축 없는 섹터(fintech·mobility 등)는 여전히 노이즈/스파이크.
- 서빙 최신일(백필일)에 카운트가 쏠려 시장섹터도 그날만 과대 → **일별 스케줄러 누적 시 자연 분산되어 해소되는 transient.**

## 8. 차기 (Pulse 품질·확장)
1. **일별 스케줄러 누적** — 카운트축에 실 시계열 형성(가장 큰 레버).
2. **시장축 가격지수화** — turnover(변동성 큼) 대신 per-ticker normalize-to-100 가격지수로 스무딩.
3. **매핑 확장** — `sector_source_map`/`_*_MAP`에 KIAT 수요기술·naver datalab·DART 섹터 추가(현재 혁신축 중심).
4. **다른 Silver(Gap/Sync)** — 동일 패턴(축 집계 SQL → 통약 → compute → 멱등 replace) 재사용.

## 9. 검증
- `scripts/pulse_scoring_test.py`(25, 회귀 — 순수함수 결정론).
- `scripts/pulse_axis_normalize_test.py`(16 — 통약 band·시장 소스맵·통화중립 융합).
- end-to-end: `POST /api/insight/pulse/refine` → silver/gold>0, `GET /api/insight/pulse` 12섹터.

> ERD 기준: [`backend/docs/erd.md`](../../../docs/erd.md) §5.0·§5.3·§6.1
