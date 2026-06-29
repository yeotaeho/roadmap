# market_insight 작업 기록 (Audit Trail)

최신 항목을 맨 위에 추가(역순). 형식은 `CLAUDE.md` [작업 기록 규칙](../../../../CLAUDE.md) 참고.

---

## 2026-06-28 — Pulse 방향성 융합 2차: shrinkage·축 가중·30일 감성 백필·배포
- **무엇** — 1차(가산 이동) 후 prod 읽기전용 검증에서 드러난 문제들을 보정하고 데이터·원격을 정렬. ① modifier에 관측수(weight)를 실어 트레일링을 관측수 가중으로 내고 `W/(W+8)` shrinkage로 단일 관측 ±1 노이즈 억제. ② 텍스트·시장을 축별로 트레일링·shrinkage 후 고정 축 가중(1:1)으로 결합 — 텍스트 행수(수천)가 시장 티커수를 압도해 시장이 묻히던 것을 해소. ③ 기존 분류행 30일치 감성 백필(`sentiment_backfill.py`). ④ 브랜치 main 머지 + `origin/main` push.
- **왜** — 1차 검증 결과 (a) 정확-일자 매칭이라 최신일 tilt 미반영(시장 06-26·활동 06-28 시차) → carry-forward, (b) modifier 60%가 ±1.0 극단(단일 관측일) → shrinkage, (c) 백필 후 텍스트 볼륨이 시장 방향을 압도하고 점수가 전 섹터 양수 쏠림 → 축 가중. 단위 테스트(합성 정렬 데이터)로는 안 잡히고 prod 실데이터 읽기전용 시뮬레이션으로만 드러난 문제들.
- **어디** — [pulse_repository.py](../hub/repositories/pulse_repository.py)(`fetch_directional_modifiers` 축 분리 반환·감성 백필 SQL·`fetch_rows_needing_sentiment`·`update_sentiment`), [pulse_pipeline.py](../hub/services/pulse_pipeline.py)(`_trailing_axis`·`compute_silver` 축 가중·shrinkage 파라미터), [sentiment_backfill.py](../../../scripts/sentiment_backfill.py)(신규, `count` 드라이런 + 청크 백필).
- **검증** — [pulse_scoring_test.py](../../../scripts/pulse_scoring_test.py) 55 PASS(shrinkage·축 결합 8건 추가). 감성 백필 prod 실행 **2,464행 전부 채움**(경제 254·담론 1130·혁신 1080, 30일 윈도우 NULL 0). prod 읽기전용 재검증: 시장 보유 섹터에 시장 하락 반영(ai-data 백필후 +7→축가중 +1·energy-climate +5→0), 전 섹터 양수 편향 해소, 12섹터 날짜 06-28 정렬. push `fee2a69..63003ad`(ff).
- **배포** — ✅ **라이브 완료**. 백엔드는 도커가 아닌 `python main.py`(uvicorn `reload=True`, :8000)로 가동 중이라, 세션 중 .py 저장 시 워커 자동 리로드(워커 23:49 시작 > 마지막 코드수정 23:46). 수동 `refine_and_serve` 1회 실행 → Gold 재생성(axis_signals 3278·modifiers 2796·gold 2997). 라이브 `GET /api/insight/pulse`가 틸트 점수 서빙 확인(food-agri 93·ai-data 46·social-service 58, 시뮬레이션 일치).
- **후속** — origin/main 이 직전 23커밋 미푸시 상태였어 함께 발행됨(`fee2a69→5496147`). 공개 prod가 별도 서버면 거기서도 동일 반영 필요. 30일 밖 행은 sentiment NULL(필요 시 윈도우 확대 재백필). 축 가중 1:1·`sentiment_k`15·`shrink_k`8·윈도우7·데드밴드0.2%는 실사용 후 재튜닝. 텍스트 감성 양수 쏠림(LLM bias) 잔존 — 섹터 평균 대비 중심화는 미적용(후속 검토).

## 2026-06-28 — Pulse 점수에 감성·시장 방향 가산 이동 융합 (방향성 modifier)
- **무엇** — 건수(활동량)만 보던 Pulse 점수에 방향성을 더한다. ① 텍스트 감성: `classify_sector` 같은 LLM 호출에 `sentiment`·`sentiment_score`(-1~1)를 얹어(토큰 0) `refined_text_sector_class` 에 적재. ② 시장 방향: `raw_market_timeseries.close_price` 전일 대비 등락(LAG·0.2% 데드밴드)을 스키마 변경 없이 SQL 산출. ③ 두 신호를 (섹터×일자) 방향성 modifier(-1~1)로 결합해, 활동 점수 위에 `score + K(15)×modifier` 가산 이동. 적용은 직전 7일 평균 + carry-forward.
- **왜** — "AI 줄도산 50건"과 "AI 투자유치 50건"이 동일하게 뜨겁게 집계되던 문제. 곱셈은 z-score 가 균일 스케일을 상쇄해 정상상태 부정 심리를 못 반영하므로 가산 이동을 택함. 정확-일자 매칭은 최신 활동일(예 06-28)에 같은 날 modifier 가 없어(시장 06-26까지·감성 희소) 사용자 화면 점수에 안 잡혀, 트레일링 평균+carry-forward 로 보정.
- **어디** — [client.py](../../../core/llm/client.py)(`_SYSTEM_PROMPT`·`_parse_classification`), [refined_text_sector_class.py](../models/bases/refined_text_sector_class.py)(컬럼 2개·제약 2개), [text_sector_classify_service.py](../hub/services/text_sector_classify_service.py)(payload), [pulse_repository.py](../hub/repositories/pulse_repository.py)(`_TEXT_SENTIMENT_SQL`·`_MARKET_DIRECTION_SQL`·`fetch_directional_modifiers`), [pulse_pipeline.py](../hub/services/pulse_pipeline.py)(`compute_silver(modifiers, sentiment_k, modifier_window_days)`·`_trailing_modifier`), [pulse_refine_service.py](../hub/services/pulse_refine_service.py)(배선). 마이그레이션 [a9d2f7c4e1b8](../../../alembic/versions/a9d2f7c4e1b8_add_sentiment_to_text_sector.py).
- **검증** — [pulse_scoring_test.py](../../../scripts/pulse_scoring_test.py) 47 PASS(modifier tilt·carry-forward·트레일링 평균·윈도우 이탈 신규), [llm_sector_classify_test.py](../../../scripts/llm_sector_classify_test.py) 24 PASS(감성 파싱), 축 18·텍스트축 8·overview 23 무회귀. prod **읽기전용** 검증(쓰기 없음) — `fetch_directional_modifiers` 2,758건 산출, 최신일 carry-forward tilt 반영(ai-data 45→33·mobility 57→44·food-agri 89→95, 데이터 없는 social-service 무변동). 마이그레이션은 prod head(`d1a2b3c4e5f6` 머지) 에 이미 적용됨.
- **후속** — `sentiment_k`(15)·`modifier_window_days`(7)·데드밴드(0.2%)·텍스트:시장 결합 가중치는 실데이터 튜닝 대상. modifier 60%가 ±1.0 극단(단일 관측일) — 관측수 가중 평균 검토. PROMPT_VERSION 미bump 라 기존 분류행 sentiment NULL(tilt 0) — 활성 섹터 즉시 효과 원하면 최근 윈도우 감성 백필. prod write 는 브랜치 미배포라 보류(배포 후 일별 잡이 자동 생성). 브랜치 `feat/pulse-sentiment-fusion`(커밋 `aa32987`·`a52ae22`).

## 2026-06-28 — 콘텐츠 신호 해상도: KOBIS 일별 박스오피스 수집기 (Phase 2 확장)
- **무엇** — KOBIS 일별 박스오피스 OpenAPI 수집기 신설. 영화 행을 `raw_economic_data`(`industry_sector='CONTENT_MEDIA'`)로 적재 → 경제 축이 content-creator 에 일별 수요 신호로 합류. `settings.kobis_api_key` + `ingest_kobis_box_office` + 일일 스케줄러 잡(`kobis_box_office`).
- **왜** — content-creator 는 이미 활성이나 신호가 discourse 뉴스 중심. 박스오피스는 실제 일별 소비(수요) 신호라 해상도를 높인다. `industry_sector` 코드(정적 매핑) 우회로 파이프라인 무변경.
- **어디** — [kobis_box_office_collector.py](../../master/hub/services/collectors/economic/kobis/kobis_box_office_collector.py)(신규), [settings.py](../../../core/config/settings.py), [bronze_economic_ingest_service.py](../../master/hub/services/bronze_economic_ingest_service.py), [scheduler.py](../../../core/scheduler.py).
- **검증** — `kobis_box_office_test` 파서 15 PASS(무키·무DB), settings/scheduler/ingest 와이어링 import 검증. ⚠️ 라이브 수집은 `KOBIS_API_KEY`(무료) 필요 — 키 설정 시 일일 스케줄러 자동 수집(키 None이면 잡 스킵). (`scheduler_refine_pipeline_test` 3건 실패는 본 변경 무관·기존 stale — 별도 태스크.)
- **후속** — 키 설정 후 1회 backfill(`days_back` 크게). 경제 축 수요 신호 혼입은 단일 score엔 무해, 추후 per-axis 해석 시 분리 검토.

## 2026-06-28 — 미달 섹터 활성화 Phase 2: 토픽 RSS 11종 → social-service 활성 (전 12섹터 활성)
- **무엇** — [news_rss_collector.py](../../../master/hub/services/collectors/discourse/news_rss/news_rss_collector.py) `_FEEDS` 에 토픽 전문지 RSS 11종 추가(복지 3·금융 3·콘텐츠 1·모빌리티 1·에듀 1·물류 1·뷰티 1). discourse 축은 LLM 섹터 분류라 피드별 섹터 매핑 불필요(category 는 메타로만).
- **왜** — Phase 1 후 남은 회색 1섹터 `social-service` 는 깨끗한 시장 티커가 없는 구조적 예외. 해법은 LLM 텍스트 축(discourse). 라이브 진단상 social-service 는 분류 누적 27건이나 윈도우 내 discourse 가 3일에 그쳐(시간 밀도 부족) 게이트 미달. 복지 전문지(웰페어뉴스·복지타임즈·정책브리핑 복지부) 일별 피드로 분산 날짜를 공급.
- **어디** — [news_rss_collector.py](../../../master/hub/services/collectors/discourse/news_rss/news_rss_collector.py) `_FEEDS`(11종 추가).
- **검증** — 11피드 live 파싱(각 50엔트리, 0 실패). 수집(`ingest_news_rss`)→discourse LLM 분류→`refine_and_serve` 후 **social-service discourse 3→11일, 회색 4→0 — 전 12섹터 활성**(market 0인데 discourse만으로 게이트 통과 = 텍스트 축 해법 실증). 타 섹터 discourse 밀도 동반 상승(mobility 5→9·content-creator 4→8·bio-health 3→9). `sector_axis_density_test` 12 PASS(무회귀).
- **후속** — KOBIS 일별 박스오피스 등 도메인 공개 API 수집기는 별도(신호 해상도 추가). RSS 피드 사망 모니터링(수집기 자동 스킵). 축 가중치 실데이터 튜닝.

## 2026-06-28 — 미달 섹터 활성화 Phase 0 진단 + Phase 1 시장축 티커 확충
- **무엇** — ① 섹터×축 신호밀도 진단 스크립트 신설(`compute_density_report` 순수함수 + 라이브 `main`). ② 미달 6섹터(핀테크·모빌리티·콘텐츠·에듀테크·물류·뷰티패션) 시장축 티커 16종을 Yahoo 수집기·`_MARKET_SOURCE_MAP` 에 추가(16→32티커). ③ 1y 백필 + pulse refine 실행으로 회색 4→1 전환 실증.
- **왜** — 미달 섹터가 "데이터 수집 중"인 근본 원인은 데이터 부재가 아니라 **시장축(일별 고밀도) 부재로 min_history 게이트(5/20일) 미달**. 라이브 진단 결과 실제 회색은 4섹터(뷰티·에듀·물류·사회서비스)였고 전부 market 신호 0일이 공통. 웹조사 적대 검증으로 확보한 일별 티커로 게이트를 메움. 정적 매핑 우회 해법은 [SECTOR_ACTIVATION_STRATEGY.md](SECTOR_ACTIVATION_STRATEGY.md) 참조.
- **어디** — 진단 [sector_axis_density_audit.py](../../../../scripts/sector_axis_density_audit.py)·[sector_axis_density_test.py](../../../../scripts/sector_axis_density_test.py)(신규), 티커 [yahoo_finance_collector.py](../../../master/hub/services/collectors/economic/yahoo/yahoo_finance_collector.py) `_UNDERCOVERED_TARGETS`, 섹터 매핑 [pulse_repository.py](../../hub/repositories/pulse_repository.py) `_MARKET_SOURCE_MAP`. 전략 문서 [SECTOR_ACTIVATION_STRATEGY.md](SECTOR_ACTIVATION_STRATEGY.md)(신규).
- **검증** — `sector_axis_density_test` 12·`pulse_scoring_test` 33·`pulse_axis_normalize_test` 18 PASS(무회귀). 신규 16티커 Yahoo 실측 응답(0 실패). **1y 백필 7,863행 upsert(0 실패) + refine 2,975행** → `beauty-fashion`·`edutech`·`logistics` 회색→활성 전환, 6섹터 모두 market 신호 14~15일 확보. `social-service` 만 잔존(깨끗한 티커 없음 — 구조적).
- **후속** — `social-service` 는 Phase 2 discourse RSS·지원사업(opportunity) 트랙으로 분리(시장 티커 없음). 핀테크·모빌리티·콘텐츠는 기존 활성이나 시장축 추가로 discourse 의존 신호 보강. ETF 글로벌 대표성·개별주 threshold·축 가중치는 실데이터 튜닝. Phase 2(토픽 RSS·KOBIS 등 공개 API)는 별도.

## 2026-06-27 — KIAT Gap youth_fit 변별 개선 + Gold 사영 단일화 (Phase 2 refine)
- **무엇** — youth_fit 앵커 루브릭+저적합 강제규칙 프롬프트(pv v3)로 변별 확보, Gold 사영을 `GapProjectionService` 단일 잡으로 분리(소스별 pv), 게이트 임계 0.5→0.4 캘리브레이션.
- **왜** — v1 youth_fit 0.6~0.7 뭉침으로 게이트 무력(45중 0건 배제). 의미 변경에 필요한 pv bump 가 공유 단일-pv 사영을 깨뜨려(타 소스 Gold 삭제) 사영 분리가 선행돼야 했음.
- **어디** — [client.py](../../../../core/llm/client.py) `_TECH_DEMAND_GAP_SYSTEM_PROMPT`, [gap_projection_service.py](../../hub/services/gap_projection_service.py)(신규), [gap_repository.py](../../hub/repositories/gap_repository.py) `project_to_gold(disc_pv, td_pv, fit_min)`·`_FETCH_SILVER_FOR_GOLD`, [tech_demand_gap_service.py](../../hub/services/tech_demand_gap_service.py)·[gap_refine_service.py](../../hub/services/gap_refine_service.py)(사영 제거), [scheduler.py](../../../../core/scheduler.py) `_job_gap_project`, [insight_routor.py](../../../../api/v1/insight/insight_routor.py) `/gap/project`, [settings.py](../../../../core/config/settings.py) `tech_demand_youth_fit_min`(0.4). 설계/계획: `backend/docs/specs/2026-06-27-kiat-gap-tech-demand-phase2-refine-design.md`·`-plan.md`.
- **검증** — `gap_chunk_test` 7·`gap_projection_test` 5·`tech_demand_gap_parse_test` 9 PASS. v3 재추출 45건 분포 0.2~0.6(avg 0.343), 게이트 20/45(44%) 하드웨어·설비 배제 → TECH_DEMAND 25 카드. discourse NEWS 213 불변(무회귀). 임계 재튜닝은 Gold 재사영만으로 적용(LLM 무). 최종 전체-브랜치 리뷰(opus) Ready to merge(Critical/Important 0). 커밋 `dd82564`~`423a741`.
- **후속** — 0.4 band 잔여 노이즈(GaN 반도체 등) 모니터링. 구 v1/v2 tech_demand Silver 정리(선택). 전체 백필(window 확대).

## 2026-06-27 — Bronze 입력 품질 권고 적용 여부 실측 + ArXiv 재수집 실현
- **무엇** — Silver(text_classify·gap·chance·causal) 입력을 좌우하는 Bronze 결손 개선 권고 4건의 코드/데이터 적용 여부를 `bronze_null_audit` 로 실측 대조. ① content_body ② gov_report 등록 ③ opportunity(K-Startup) 본문 ④ innovation 비-KIAT 수집량. ④의 ArXiv는 페이지네이션 수정(`1b53350`)이 코드에만 있고 데이터 미반영(06-08 기준 29건)임을 확인 → `_job_arxiv_papers()` 수동 트리거로 재수집 실현.
- **왜** — 붙여둔 이전 분석이 content_body 재수집·gov_report 등록 이전 시점이라 stale. 코드 머지 ≠ 데이터 반영이라 실데이터로 권고 적용 여부를 검증하고, 미반영분(ArXiv)을 실현해 신호를 가동.
- **어디** — 측정 [bronze_null_audit.py](../../../../scripts/bronze_null_audit.py), 트리거 [scheduler.py](../../../../core/scheduler.py) `_job_arxiv_papers`(→ `BronzeInnovationIngestService.ingest_arxiv`), 수집기 [arxiv_papers_collector.py](../../../master/hub/services/collectors/innovation/arxiv/arxiv_papers_collector.py).
- **검증** — 실측: content_body NULL 36.2%→**0.2%**(평균 887자), `DISCOURSE_GOV_REPORT` **50건**(스케줄러 412·685행 등록 확인), KSTARTUP raw_content 평균 **130자**(오늘 수집). ArXiv 재수집: before 29 → fetched 735·inserted 643 → **after 672건**(11개 중 10개 성공, `econ.EM` 1개 429 레이트리밋). 권고 1·2·3은 이미 적용 완료, 4는 본 작업으로 실현.
- **후속** — ⚠️ ArXiv 11개 카테고리 빠른 페이지네이션 시 arxiv.org 429 발생(econ.EM 누락) — 카테고리 간 딜레이 추가 검토(현재 카테고리별 예외 격리로 부분 성공). 적재된 643건은 다음 `insight_refine` 파이프라인에서 Silver(text_classify→tech_demand 축·Gap)로 흐름. Customs 26·KISTEP 4는 월간 HS·소량 소스라 구조적 소량(결함 아님). opportunity raw_content 61.6%<200자는 K-Startup 130자 요약·입찰 메타 특성(구조적).

## 2026-06-27 — KIAT 수요기술 → Gap 청년 기회 신호 (Phase 2)
- **무엇** — 분류된 KIAT/KISTEP를 LLM 추출해 "기업 미확보 수요기술 → 청년 기회" Gap 신호로 변환. ① `extract_tech_demand_gap` + youth_fit(0~1) 파서·프롬프트. ② `refined_gap_insights.youth_fit_score` 컬럼 + `tech_demand_youth_fit_min`(0.5) 설정. ③ `GapRepository` 소스-인지 일반화(`fetch_unprocessed_tech_demand`·`upsert_silver` 파라미터화·Gold evidence COALESCE/youth_fit 게이트·evidence_type 'TECH_DEMAND'). ④ `TechDemandGapService`(PROMPT_VERSION 'v1' 공유). ⑤ 스케줄러 `_job_tech_demand_gap`을 gap_refine 다음 등록.
- **왜** — Phase 1은 KIAT를 Pulse tech_demand 축으로만 소비. KIAT 수요기술=시장 미해결 갭이라 Gap 탭 신규 신호원으로 전환. youth_fit 게이트로 청년 무관 B2B 설비·자본집약 기술 배제 의도.
- **어디** — [client.py](../../../../core/llm/client.py) `extract_tech_demand_gap`·`_TECH_DEMAND_GAP_SYSTEM_PROMPT`·`_parse_tech_demand_gap`, [refined_gap_insights.py](../../models/bases/refined_gap_insights.py) `youth_fit_score` + 마이그레이션 `d7a1f3c9e2b5`, [settings.py](../../../../core/config/settings.py) `tech_demand_youth_fit_min`, [gap_repository.py](../../hub/repositories/gap_repository.py) `fetch_unprocessed_tech_demand`·`_FETCH_SILVER_FOR_GOLD`·`project_to_gold`, [tech_demand_gap_service.py](../../hub/services/tech_demand_gap_service.py)(신규), [scheduler.py](../../../../core/scheduler.py) `_job_tech_demand_gap`. 설계/계획: `backend/docs/specs/2026-06-27-kiat-gap-tech-demand-phase2-design.md`·`-plan.md`.
- **검증** — 파서 `tech_demand_gap_parse_test.py` 9 PASS. 소규모 백필(limit 100): scanned 45·gaps 45·skipped 0·issues 258. 무회귀: gap_refine 서비스 무수정 + `upsert_silver` setdefault + `project_to_gold` fit_min=0.0 기본 → DISCOURSE_SIGNAL 280→280. 최종 전체-브랜치 리뷰(opus) Ready to merge(Critical/Important 0). 커밋 `b452739`~`f9f2e86`, 병합 `139e422`.
- **후속** — ⚠️ youth_fit 분포 퇴화 관측(45건 min 0.6·max 0.7·avg 0.696, 0.6 미만 0건 → 임계 0.5/0.7 어디서도 의미 있는 분리 없음). KIAT 산업기술 수요에 청년 무관 B2B가 상당수일 텐데 저점수가 전무 → **프롬프트가 변별 못 함**. 임계 튜닝만으로 불가, 프롬프트 개선(저/고적합 few-shot·루브릭) + `PROMPT_VERSION` bump 재추출 필요(별도 spec). 현재 임계 0.5 유지(무해 통과). 전체 window 백필은 프롬프트 개선 후. Gold 이중사영 단일화(현재 멱등 무해).

## 2026-06-27 — LLM refine 4서비스 + embed 청크 커밋으로 idle timeout 방지 (Phase 2)
- **무엇** — `gap·chance·causal·investment` refine 서비스 루프에 `REFINE_CHUNK=25` 중간 commit 추가. `embed_service` 는 기존 `_BATCH=64` 루프 끝마다 commit 이동(doc·user 양쪽). Gold 사영(`project_to_gold`)은 루프 종료 후 그대로 유지.
- **왜** — Phase 1 에서 text_sector_classify 에 적용한 청크 커밋 수정의 연속. 동일 패턴([fetch → 다회 `await llm.*` → 마지막 1회 commit])을 가진 4 서비스가 큰 배치(limit=200)에서 LLM idle 이 `pool_recycle`(5분)을 초과해 `asyncpg ... connection is closed` 로 실패하는 구조적 결함.
- **어디** — [gap_refine_service.py](../../hub/services/gap_refine_service.py) `REFINE_CHUNK`, [chance_refine_service.py](../../hub/services/chance_refine_service.py) `REFINE_CHUNK`, [causal_chain_service.py](../../hub/services/causal_chain_service.py) `REFINE_CHUNK`, [investment_flow_service.py](../../hub/services/investment_flow_service.py) `REFINE_CHUNK`, [embed_service.py](../../hub/services/embed_service.py) `embed_documents`·`embed_users`. 테스트: `scripts/gap_chunk_test.py`·`chance_chunk_test.py`·`causal_chunk_test.py`·`invest_chunk_test.py`·`embed_chunk_test.py`(신규).
- **검증** — 신규 청크 테스트 5종 34항목 PASS, 기존 회귀(`llm_gap_extract_test` 12·`llm_investment_extract_test` 13·`causal_test` 10·`text_classify_chunk_test` 5) 40항목 PASS. 커밋 `f98b967`.
- **후속** — `pool_recycle` 초과 위험 있는 서비스 전수 패치 완료. 가중치·배치 크기 튜닝은 실데이터 관찰 후.

## 2026-06-27 — KIAT 수요기술 → Pulse tech_demand 축 연결 + 분류 청크 커밋 (Phase 1)
- **무엇** — innovation 96%(KIAT 11,226건) 미소비 dead data 를 Pulse `tech_demand` 축으로 연결. ① pulse_pipeline `DEFAULT_AXIS_WEIGHTS` 에 `tech_demand` 0.5. ② text_classify `_TARGET_TABLES` 에 raw_innovation_data + `_FETCH_UNCLASSIFIED_INNOVATION`(KIAT·KISTEP만, title+abstract+keyword, collected_at 기준). ③ `_TEXT_SECTOR_AXIS_SQL` 에 tech_demand UNION. ④ `classify_unclassified` 청크 커밋(`CLASSIFY_CHUNK=25`)으로 연결 idle timeout 버그 수정.
- **왜** — KIAT 는 자유 keyword 라 `sector_source_map` 고정 매핑 불가 → innovation 축 제외 → 96% 미활용. LLM 섹터분류 재사용으로 트렌드 신호화. 백필 중 큰 배치 LLM idle 이 DB 연결 `pool_recycle`(5분)을 초과해 `connection closed` 발견 → 청크 커밋 근본 수정(daily 잡도 보호).
- **어디** — [pulse_pipeline.py](../../hub/services/pulse_pipeline.py) `DEFAULT_AXIS_WEIGHTS`, [text_sector_classify_service.py](../../hub/services/text_sector_classify_service.py) `_TARGET_TABLES`·`CLASSIFY_CHUNK`·`classify_unclassified`, [pulse_repository.py](../../hub/repositories/pulse_repository.py) `_FETCH_UNCLASSIFIED_INNOVATION`·`_TEXT_SECTOR_AXIS_SQL`. 설계/계획: `backend/docs/specs/2026-06-27-kiat-pulse-tech-demand-design.md`·`backend/docs/plans/2026-06-27-kiat-pulse-tech-demand.md`.
- **검증** — `pulse_scoring_test` 33·`text_classify_chunk_test` 5·`llm_sector_classify_test` 14 PASS, `kiat_pulse_integration_test`(실 DB) 3 PASS. 소량 백필 후 tech_demand 0→8건, 100건 무에러(연결 안전). 커밋 `9b50796`·`558229e`·`6c0e76d`·`decf080`(설계 `a2b6447` 외).
- **후속** — 전체 11,226건 백필은 고쳐진 daily 가 점진 처리. 가중치 0.5 는 휴리스틱(실데이터 튜닝). ⚠️ 동일 idle 버그가 gap·chance·causal·investment refine 서비스에도 존재(`task_6b17a37b` 플래그). Phase 2: 분류된 KIAT 를 Gap 기회 신호로(별도 spec).

## 2026-06-26 — 투자 금액 추출 Silver 수직 신설 (③a)
- **무엇** — `refined_investment_flows` Silver 수직 신설. 투자/펀딩/M&A/IPO 성격 economic 헤드라인을 LLM(`extract_investment`)으로 금액(KRW)·통화·단계·기업 추출해 멱등 적재. 평가 ③ "투자흐름 금액 None(반쪽 신호)" 보강.
- **왜** — 1순위 지표 "투자흐름"의 *강도(금액)*가 거의 비어("어느 섹터에 자본이 얼마나" 정량화 불가) 있던 갭.
- **어디** — [client.py](../../../core/llm/client.py) `extract_investment`·`_parse_investment`·`_INVESTMENT_SYSTEM_PROMPT`, [refined_investment_flows.py](../../models/bases/refined_investment_flows.py), [investment_flow_service.py](../../hub/services/investment_flow_service.py), [investment_repository.py](../../hub/repositories/investment_repository.py), 마이그레이션 `c5f9a3b7d1e2`, 스케줄러 `_job_investment_refine`(파이프라인 entity_extract 뒤).
- **검증** — `llm_investment_extract_test`(13)·`scheduler_refine_pipeline_test`(5) PASS, ORM import OK. 커밋 `5ec06cc`·`fd8cd70`·`0dbc5b9`. ⚠️ **마이그레이션 미적용**(DB 없음) — 배포 시 `alembic upgrade head`(`c5f9a3b7d1e2`) 필수, 미적용 시 잡 실패.
- **후속** — 환율 추정 금지로 외화 전용 기사는 amount null(abstain). 섹터는 `refined_text_sector_class` 조인으로 도출(현재 sector_slug null). Pulse market 축/서빙 연결은 별도. ALIO 사업비·NPS 보유금액(③b)은 live 검증 필요.

## 2026-06-26 — 데이터 퀄리티 수정(Sync 신뢰도·Pulse 정규화·Chance 매칭)
- **무엇** — Bronze·Silver 퀄리티 평가 후 3개 Silver 결함 수정. ② Sync 적합도: 사용자별 min-max→전역 절대 스케일(`scale_affinity`)+스프레드 충분성 게이트(`has_sufficient_signal`)+"데이터 부족" 중립 배지, 원시 코사인 보존. ④ Pulse 축 정규화: min/max→5/95 퍼센타일 윈저화+클립(`_percentile`)로 단발 스파이크의 섹터 간 전이 차단. ⑤a Chance 매칭: 부분문자열→pgvector 코사인 의미 매칭(`fetch_match_affinities`·`semantic_match_score`)+키워드 폴백.
- **왜** — 평가 결과 "그럴듯하지만 신뢰 못 할 숫자"(thin-data 노이즈를 확신 배지로, 스파이크 전이, 임의적 매칭) 리스크 식별.
- **어디** — [sync_refine_service.py](../../hub/services/sync_refine_service.py), [pulse_repository.py](../../hub/repositories/pulse_repository.py) `_normalize_axes`, [chance_match_service.py](../../hub/services/chance_match_service.py), [chance_repository.py](../../hub/repositories/chance_repository.py) `_FETCH_MATCH_AFFINITIES`
- **검증** — `sync_score_test`(17)·`pulse_axis_normalize_test`(18)·`pulse_scoring_test`(31)·`chance_extract_match_test`(21) 전부 PASS. 커밋 `f3881c8`·`308d6b5`·`2b2f2e9`.
- **후속** — 절대 스케일 앵커(AFFINITY_LO/HI·CHANCE_COS_LO/HI)는 휴리스틱 → 실데이터로 튜닝. ③ 투자 금액 해상도·⑤b 직무 수요 소스는 설계/키 필요(미착수). 원시 코사인 정밀 보존은 affinity_raw 컬럼 마이그레이션 검토.

## 2026-06-26 — Sync 추이 엔드포인트 + 대시보드 재설계 연동
- **무엇** — `GET /api/sync/scores/history`(일자별 섹터 평균 = 전체 싱크 추이) 신설. 프론트 대시보드 재설계(Pulse 히어로+점진공개, 섹터 스파크라인, 인과 가로 플로우, Sync 원형 게이지+추이)와 연동.
- **왜** — 대시보드 정보위계·시각화 약점(빈약한 viz·평평한 위계) 개선 + 타 서비스(Exploding Topics·Lightcast·Koyfin) 패턴 차용. Sync 추이 표시에 이력 서빙 필요.
- **어디** — [sync_routor.py](../../../api/v1/sync/sync_routor.py) `get_sync_score_history`, [sync_repository.py](../../../hub/repositories/sync_repository.py) `fetch_score_history`(`_FETCH_SCORE_HISTORY`). 프론트: `www.yeotaeho.kr` PulseTab·PulseViz·DashboardView·dashboard.ts·useDashboard.ts.
- **검증** — 백엔드 `py_compile` 통과, 프론트 `tsc --noEmit` 통과. 커밋 `d6ce714`·`da436e9`·`f1c5f20`·`953f699`. ⚠️ DB·인증 필요한 런타임 테스트는 미실행(쿼리·라우팅만 구조 검증).
- **후속** — 진짜 개인화 한 줄(Pulse↔Sync 교차), 섹터 드릴다운 페이지(`/pulse/{sector}/history` 미연결), Chance 저장 영속화(wallet 도메인 스텁) 미구현.

## 2026-06-26 — 문서 동기화(erd.md·STATUS.md SSOT 갱신)
- **무엇** — `erd.md` §0 에 2026-06-26 갱신 블록 추가(파일 head `b8e4c2a6f1d9`, 인사이트 6수직 Silver/Gold 정의 반영, 미문서 테이블 2종·런타임 산출 2종 명시) + v2.9 footer. `MARKET_INSIGHT_IMPLEMENTATION_STATUS.md` head·잡 체인 직렬화·Causal/Briefing 라이브 반영.
- **왜** — 문서가 코드보다 1~2단계 뒤처져 SSOT 신뢰도 하락(head `f8c2e6a0d3b7`/`e2c5a7b9d3f4` stale, Causal·Briefing 라이브 미반영).
- **어디** — [erd.md](../../../docs/erd.md), [MARKET_INSIGHT_IMPLEMENTATION_STATUS.md](./MARKET_INSIGHT_IMPLEMENTATION_STATUS.md)
- **검증** — 문서 변경(코드 무관). head 그래프는 `alembic/versions` down_revision 추적으로 확인(`b8e4c2a6f1d9` 단일 head).
- **후속** — Neon 실제 적용 head 는 `alembic current` 로 별도 확인. `refined_text_sector_class`·`refined_causal_chain_insights` 를 erd 정식 절로 편입.

## 2026-06-26 — 일일 정제 체인 직렬화 (3c)
- **무엇** — 11개 정제 잡(`text_classify`…`sync_refine`)을 `_REFINE_PIPELINE` 순차 실행 `insight_refine` 단일 잡으로 묶음. `run_job_now` 에 개별 스텝 폴백 추가.
- **왜** — 동일 cron 으로 개별 등록돼 `AsyncIOScheduler` 가 동시 제출 → Silver→Gold 의존 순서 미보장(레이스).
- **어디** — [scheduler.py](../../../core/scheduler.py) `_REFINE_PIPELINE`·`_job_insight_refine_pipeline`·`run_job_now`
- **검증** — `python scripts/scheduler_refine_pipeline_test.py` → PASS=5 FAIL=0. 커밋 `bd45afa`.
- **후속** — Bronze→refine 시차(같은 트리거)는 멱등 다음날 보정 설계 유지. 필요 시 refine 트리거 시각 분리 검토.

## 2026-06-26 — Sync·Chance 사용자별 서빙 IDOR 차단 (3b)
- **무엇** — `GET /sync/scores`·`/chance/matches` 의 `user_id` 쿼리 파라미터를 공용 인증 의존성 `get_authenticated_user_id`(Bearer JWT)로 대체.
- **왜** — `user_id` 를 쿼리로 신뢰해 타 사용자 점수 조회(IDOR) 가능.
- **어디** — [api_guards.py](../../../core/api_guards.py) `get_authenticated_user_id`, [sync_routor.py](../../../api/v1/sync/sync_routor.py), [chance_routor.py](../../../api/v1/chance/chance_routor.py)
- **검증** — `python scripts/auth_user_dep_test.py` → PASS=5 FAIL=0. 커밋 `aee1531`.
- **후속** — 프론트(`useDashboard.ts`)가 Sync/Chance 호출 시 `user_id` 쿼리 대신 Authorization 헤더로 전환 필요. `user_routor.get_current_user_id` 중복 제거(공용 의존성으로 통합) 검토.

## 2026-06-26 — refine/match 내부 토큰 가드 (3a)
- **무엇** — 무인증 배치 트리거 7개 엔드포인트(insight `pulse`/`briefing`/`causal`/`gap` refine, sync refine, chance refine/match)에 `X-Internal-Token` 가드 적용. 키 미설정 시 fail-closed(503).
- **왜** — 인증 없이 LLM 배치·DB 재생성을 누구나 트리거 가능(비용·무결성 리스크).
- **어디** — [api_guards.py](../../../core/api_guards.py) `require_internal_token`, [settings.py](../../../core/config/settings.py) `internal_api_key`, insight/sync/chance 라우터
- **검증** — `python scripts/internal_token_guard_test.py` → PASS=7 FAIL=0. 커밋 `9b1ffb8`.
- **후속** — 운영 `.env` 에 `INTERNAL_API_KEY` 설정. 스케줄러는 서비스 직접 호출이라 가드 무관.
