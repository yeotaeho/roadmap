# Master Bronze 구현 현황 SSOT

> 기준일: 2026-06-07
>
> 이 문서는 `backend/domain/master`, `backend/api/v1/master/master_routor.py`,
> `backend/core/scheduler.py`의 현재 코드 기준 구현 현황을 기록한다.

## 1. 실제 아키텍처

```text
FastAPI router
  -> Bronze*IngestService
    -> source Collector
      -> Pydantic DTO
        -> Repository
          -> PostgreSQL Bronze table
```

| 계층 | 실제 경로 |
|------|-----------|
| API | `backend/api/v1/master/master_routor.py` |
| 스케줄러 | `backend/core/scheduler.py` |
| 서비스 | `backend/domain/master/hub/services/bronze_*_ingest_service.py` |
| 컬렉터 | `backend/domain/master/hub/services/collectors/` |
| Pydantic DTO | `backend/domain/master/models/transfer/` |
| SQLAlchemy 모델 | `backend/domain/master/models/bases/` |
| Repository | `backend/domain/master/hub/repositories/` |

현재 `spokes/retreivers`, `hub/orchestrator`, `hub/routing`은 실질 구현 경로가 아니다.

## 2. 현재 물리 적재 테이블

| 테이블 | 실제 구현 |
|--------|-----------|
| `raw_economic_data` | 경제 이벤트뿐 아니라 정책, 특허, 검색 수요 신호도 임시 통합 적재 |
| `raw_market_timeseries` | Yahoo 16종 티커의 일별 OHLCV 연속 시계열 |
| `raw_opportunity_data` | SMES 중소벤처기업부 사업공고 |
| `raw_innovation_data` | ERD에는 존재하지만 master 수집 파이프라인 미구현 |
| `raw_people_data` | ERD에는 존재하지만 master 수집 파이프라인 미구현 |
| `raw_discourse_data` | ERD에는 존재하지만 master 수집 파이프라인 미구현 |

| 신호 | 논리 분류 | 현재 물리 적재 |
|------|-----------|----------------|
| KIPRIS 특허 트렌드 | Innovation | `raw_economic_data` |
| Naver DataLab 검색량 | People/Demand | `raw_economic_data` |

전용 Bronze 테이블로 이관하려면 DTO, 모델, repository, migration, API와 Silver 입력 계약을 함께 변경해야 한다.

## 3. 저장 계약과 멱등성

모든 Collector 출력은 Pydantic 모델로 검증한다.

| 파이프라인 | DTO | 멱등 키 | 저장 방식 |
|------------|-----|---------|-----------|
| Economic | `EconomicCollectDto` | `source_url` | `ON CONFLICT DO NOTHING` |
| Market timeseries | `MarketTimeseriesDto` | `(ticker, trade_date)` | `ON CONFLICT DO UPDATE` |
| Opportunity | `OpportunityCollectDto` | `source_url` | `ON CONFLICT DO NOTHING` |

`raw_economic_data.source_url`은 실제 URL뿐 아니라 `ecos://...` 같은 합성 식별자도 허용한다.
원문·원응답·정량 보조값은 `raw_metadata`에 보존하고 의미 분류와 교차 분석은 Silver 책임으로 둔다.

## 4. 구현된 수집기

### 4.1 `raw_economic_data`

| 소스 | 컬렉터 | API | 스케줄 |
|------|--------|-----|--------|
| DART 주요사항보고(B)·지분공시(D) | `dart_collector.py` | `/api/master/bronze/economic/dart` | 일 |
| DART 정기공시(A) R&D/CAPEX | `dart_periodic_collector.py` | `/api/master/bronze/economic/dart-periodic` | 주 |
| DART IPO 발행공시(C) | `dart_ipo_collector.py` | `/api/master/bronze/economic/dart-ipo` | 일 |
| 국민연금 DART 포트폴리오 | `nps_dart_collector.py` | `/api/master/bronze/economic/nps-portfolio` | 일 |
| Wowtale RSS | `wowtale_collector.py` | `/api/master/bronze/economic/wowtale` | 일 |
| Wowtale archive | `wowtale_archive_crawler.py` | `/api/master/bronze/economic/wowtale-archive` | 수동 |
| Platum RSS | `platum_collector.py` | `/api/master/bronze/economic/platum` | 일 |
| Venturesquare RSS | `venturesquare_collector.py` | `/api/master/bronze/economic/venturesquare` | 일 |
| StartupRecipe RSS | `startup_recipe_collector.py` | `/api/master/bronze/economic/startup-recipe` | 일 |
| Yahoo volume surge | `yahoo_finance_collector.py` | `/api/master/bronze/economic/yahoo-finance` | 주 |
| Yahoo macro surge | `yahoo_macro_collector.py` | `/api/master/bronze/economic/yahoo-macro` | 주 |
| BOK ECOS | `bok_ecos_collector.py` | `/api/master/bronze/economic/bok-ecos` | 주 |
| ALIO 공공기관 사업 | `alio_public_inst_project_collector.py` | `/api/master/bronze/economic/alio` | 주 |
| 보조금24 | `subsidy24_collector.py` | `/api/master/bronze/economic/subsidy24` | 일 |
| MSIT 보도자료·사업공고 | `msit_bbs_collector.py` | `/api/master/bronze/economic/msit-*` | 일 |
| MSIT R&D 예산 HWPX | `msit_publicinfo_63_collector.py` | `/api/master/bronze/economic/msit-rnd-budget` | 일 |
| MFDS 보도자료 | `mfds_bbs_collector.py` | `/api/master/bronze/economic/mfds-press` | 일 |
| MSS 보도자료 | `mss_bbs_collector.py` | `/api/master/bronze/economic/mss-press` | 일 |
| MOEF 로컬 문서 | `moef_local_pdf_collector.py` | `/api/master/bronze/economic/moef-*` | 수동 |
| Naver DataLab | `naver_datalab_collector.py` | `/api/master/bronze/economic/naver-datalab` | 주 |
| KIPRIS 특허 트렌드 | `kipris_patent_collector.py` | `/api/master/bronze/economic/kipris-patents` | 주 |

### 4.2 기타 Bronze

| 테이블 | 소스 | API | 스케줄 |
|--------|------|-----|--------|
| `raw_market_timeseries` | Yahoo 16종 OHLCV | `/api/master/bronze/market-timeseries/yahoo` | 일 |
| `raw_opportunity_data` | SMES 사업공고 | `/api/master/bronze/opportunity/smes` | 일 |

## 5. 스케줄러

`SCHEDULER_ENABLED=true`일 때 FastAPI lifespan에서 APScheduler를 시작한다.

- 기본 시간대: `Asia/Seoul`
- 일일 기본 시각: `09:00`
- 주간 기본 시각: 월요일 `09:00`
- 공통 옵션: `max_instances=1`, `coalesce=True`, `misfire_grace_time=3600`
- 잡별 독립 `AsyncSession`
- API 키가 없는 잡은 실패시키지 않고 skip
- MOEF 업로드와 backfill 작업은 자동 스케줄 대상이 아니다.

운영 API:

- `GET /api/master/scheduler/jobs`
- `POST /api/master/scheduler/jobs/{job_id}/run`

## 6. 필요한 환경 변수

| 기능 | 환경 변수 |
|------|-----------|
| DART | `DART_API_KEY` 또는 `OPENDART_API_KEY` |
| SMES | `SMES_SERVICE_KEY` 또는 `SMES_API_KEY` |
| ALIO | `ALIO_SERVICE_KEY` 또는 `ALIO_API_KEY` |
| BOK ECOS | `BOK_ECOS_API_KEY` 또는 `BOK_ECOS_SERVICE_KEY` |
| 보조금24 | `SUBSIDY24_SERVICE_KEY` 또는 `SUBSIDY24_API_KEY` |
| KIPRIS | `KIPRIS_API_KEY` 또는 `KIPRIS_SERVICE_KEY` |
| Naver DataLab | `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET` |
| 스케줄러 | `SCHEDULER_ENABLED`, `SCHEDULER_TIMEZONE`, `SCHEDULER_DAILY_AT`, `SCHEDULER_WEEKLY_DOW`, `SCHEDULER_WEEKLY_AT` |

## 7. 아직 구현되지 않은 주요 범위

- K-Startup 통합공고
- SMES 선정 결과와 실제 집행 현황
- KONEPS 입찰 공고
- KVIC 시장 집계
- FSS/KOFIA 사모펀드 결성·운용
- BOK 정책 보도자료, KOCCA/KHIDI, FSC, MOTIE, ME 등 추가 부처 보도자료
- `raw_innovation_data`, `raw_people_data`, `raw_discourse_data` 전용 ingest 파이프라인
- Silver/Gold 자동 정제·집계

## 8. 문서 우선순위

1. 본 문서: 현재 구현·API·스케줄 SSOT
2. `backend/docs/DATA_COLLECTION_SOURCES_GUIDE_V3.md`: 논리적 출처 카탈로그와 목표 분류
3. `backend/docs/erd.md`: 목표 데이터 모델
4. 개별 Collector 문서: 소스별 파싱·운영 세부사항
5. `ECONOMIC_DATA_SOURCE_STATUS.md`, `ECONOMIC_FLOW_IMPLEMENTATION_ROADMAP.md`: 과거 의사결정과 구현 이력
