# trending_keywords 즉석 서빙 — 설계 (Spec)

> 작성 2026-06-25. market_insight 도메인. 잠자는 `refined_innovation_signal.extracted_keywords`(LLM 추출 키워드, 미소비)를 집계해 PulseTab의 **키워드 티커 + 급상승 키워드 클라우드** 섹션을 복원한다. LLM·새 테이블·마이그레이션 없음(즉석 집계).

## 0. 목표 & 성공 기준
- `GET /api/insight/keywords` 가 `{cloud[], ticker[]}` 를 명세대로 응답.
- 순수함수 `assemble_keywords()` 무DB 테스트 `FAIL=0`.
- PulseTab에 **트렌딩 키워드** 섹션(TICKER + CLOUD) 라이브 렌더, `tsc` 통과.
- 데이터 희소 시 빈 상태(PanelStatus), 수치 결정론.

## 1. 접근
즉석 집계(Pulse overview 선례). 원천 Silver `refined_innovation_signal`(`extracted_keywords` JSONB str 배열·`reference_period_end`·`sector_slug`)를 SQL unnest·집계. ERD의 Gold `trending_keywords` 테이블 적재(잡)는 비범위.

## 2. API 계약
`GET /api/insight/keywords?window_days=30&cloud_limit=30&ticker_limit=12&sector=<optional>`
```jsonc
{
  "success": true,
  "cloud":  [ { "keyword": "LLM", "weight": 18, "rank": 1 } ],            // 빈도 내림차순
  "ticker": [ { "keyword": "RAG", "value_label": "+27%", "delta_pct": 27, "rank": 1 },
              { "keyword": "온디바이스AI", "value_label": "신규", "delta_pct": null, "rank": 2 } ]
}
```
- 시간축 `reference_period_end`. 선택 `sector`로 `sector_slug` 필터(기본 전체).

## 3. 집계 정의 (결정론, LLM 0)
- **빈도(df)** = 키워드를 담은 **신호 수**(distinct signal). recent 윈도우 `[today−window, today]`, prior 윈도우 `[today−2·window, today−window]`.
- **CLOUD** = recent df 내림차순 상위 `cloud_limit`. `weight`=df, `rank`=순위. 동률 keyword 사전순.
- **TICKER(상승 델타)**:
  - recent df < `ticker_min_recent`(기본 2) 제외(노이즈 컷).
  - `delta_pct = round((recent−prior)/prior×100)` (prior>0). prior=0 → **신규**(`delta_pct=null`).
  - **상승만 포함**: `delta_pct>0` 또는 신규. (하락·보합 제외.)
  - 정렬: 신규(∞) → 큰 델타 → recent df → keyword 사전순. 상위 `ticker_limit`. `value_label`=`"+{delta}%"` 또는 `"신규"`.

## 4. 리포지토리 / 순수함수
- `SignalRepository.fetch_keyword_freqs(window_days, sector) -> (recent: dict[str,int], prior: dict[str,int])` — 2개 윈도우 각각 `jsonb_array_elements_text` unnest + `GROUP BY kw`로 `count(DISTINCT id)` df 집계. asyncpg-safe: 정수 윈도우 `make_interval(days => :n)`, nullable sector는 `CAST(:sector AS TEXT) IS NULL OR sector_slug = :sector`.
- `assemble_keywords(recent, prior, cloud_limit, ticker_limit, ticker_min_recent) -> {"cloud":[...], "ticker":[...]}` — **DB 비의존 순수함수**(신규 `hub/services/keyword_trends.py`). §3 랭킹·델타·라벨 조립. 단위 테스트 대상.

## 5. 프론트
- `dashboard.ts`: `fetchTrendingKeywords()` + 타입(`KeywordCloudItem`·`KeywordTickerItem`·`TrendingKeywords`).
- `useDashboard.ts`: `useTrendingKeywords()`(staleTime 5분·retry 1).
- `PulseTab.tsx`: **트렌딩 키워드** 섹션 추가 — TICKER(키워드+델타 배지 가로 리스트) + CLOUD(빈도 비례 글자 크기 단어구름). `PanelStatus`로 로딩/에러/빈 처리.

## 6. 에러·엣지
- 데이터 전무/희소 → `cloud=[]`·`ticker=[]` → PanelStatus 빈 상태. prior 윈도우 비면 대부분 "신규"(정직).
- `extracted_keywords` null/빈 배열 신호는 자연 제외.
- 참고: `refined_innovation_signal`은 entity_extract LLM 잡이 소량만 실행돼 희소할 수 있음(sparse-tolerant 설계).

## 7. 테스트
- `scripts/keyword_trends_test.py` — `assemble_keywords()` 합성 입력: (1) 정상 빈도/델타, (2) 신규(prior=0), (3) 상승만(하락 제외), (4) min_recent 노이즈 컷, (5) 전무→빈배열, (6) 동률 사전순 결정론. `FAIL=0`.
- `tsc` + 라이브(앱 엔드포인트, Pulse 선례).

## 8. 비범위
economic_briefings·causal_chains·crossover_metrics·Gold `trending_keywords` 테이블 적재(잡)·source_count 가중·섹터별 분리 뷰.
