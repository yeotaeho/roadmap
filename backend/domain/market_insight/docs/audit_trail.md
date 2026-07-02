# market_insight 작업 기록 (Audit Trail)

최신 항목을 맨 위에 추가(역순). 형식은 `CLAUDE.md` [작업 기록 규칙](../../../../CLAUDE.md) 참고.

---

## 2026-07-02 — SP-3: 자기모델 추천 반영 + LLM 설명 레이어
- **무엇** — (1) 자기모델(RIASEC 라벨·서사·비민감 긍정 근거 top10)을 `build_user_embed_text` 직렬화에 통합(1000자 캡 내장·캡 후 해시)하고, 재임베딩 후보를 `users` 기준으로 재구성해 **프로필 없는 코치-only 사용자도 임베딩·매칭 대상**에 포함. (2) Gold 2테이블에 설명 컬럼(`sync_scores_daily.explanation`·`user_chance_matches.match_explanation`, 마이그 `a6af4387ed37`) + 재점수 upsert 시 입력 불변이면 보존/변경이면 NULL 무효화 CASE + 서빙 노출. (3) `LlmClient.explain_recommendations`(+닫힌 스키마 파서 `_parse_recommend_explain`, 200자 클램프)와 `RecommendExplainService` 일일 배치 — **사용자당 LLM 1회**로 Sync 상위 3섹터+Chance 상위 10매치 설명 생성(SQL 캡 선별·TOCTOU 가드·per-user 격리), `_REFINE_PIPELINE` 마지막 등록. dislike 근거는 프롬프트로 전달해 충돌 시 주의 문구 포함(감점 없음). (4) 프론트 Sync 행·Chance 카드에 설명 서브텍스트(`match_explanation ?? match_reason` 폴백). **민감 근거는 임베딩·프롬프트 어디에도 미주입**(리포 필터 + 반증 검증 테스트).
- **왜** — SP-1/2b로 쌓인 자기모델이 추천을 실제로 바꾸고 "왜 이 추천인지"가 보여야 "AI 상담실=개인화 본가" 루프가 닫힘. 폼을 안 채워도 코치와 대화하면 Sync/Chance 신호가 두꺼워지는 비전의 완성.
- **어디** — [user_embed_text.py](../hub/services/user_embed_text.py)(`RIASEC_LABEL`·`self_model_terms`·`EMPTY_EMBED_TEXT`) · [embed_repository.py](../hub/repositories/embed_repository.py)(후보 재구성·긍정 근거 조회·touch/clear/delete 무효화 계열) · [embed_service.py](../hub/services/embed_service.py) · [chance_repository.py](../hub/repositories/chance_repository.py)(사용자 확장·CASE·공고 문안 변경 무효화) · [sync_repository.py](../hub/repositories/sync_repository.py)(CASE·서빙) · [core/llm/client.py](../../../core/llm/client.py) · [recommend_explain_repository.py](../hub/repositories/recommend_explain_repository.py)·[recommend_explain_service.py](../hub/services/recommend_explain_service.py)(신규) · [scheduler.py](../../../core/scheduler.py) · 프론트 `dashboard.ts`·`DashboardView.tsx`. 스펙 [design](../../../docs/superpowers/specs/2026-07-02-self-model-recommend-explain-design.md)·플랜 [plan](../../../docs/superpowers/plans/2026-07-02-self-model-recommend-explain.md)·ERD §sync/chance 컬럼 반영.
- **검증** — SDD 5태스크 각 리뷰 Approved(Task4 리뷰가 플랜 시드 버그 — 민감 미주입 테스트가 dimension 화이트리스트에 가려 허위 검증 — 적발, 반증 검증까지 수행) + whole-branch(opus) Ready:Yes. **Codex 12라운드**: 실결함 P1 1건(uuid expanding bind 무타입)·P2 11건 수정 — 유저캡 SQL 하강, `'_'` 폴백 임베딩 차단·신호 소실 정리, 설명 무효화 계열(공고 문안 변경·임베딩 실갱신·당일 Sync 대칭·dislike 트리거+워터마크 touch·TOCTOU 가드), 자격 조건 한정(빈 자기모델·dislike-only·빈 프로필 행). **반증 유지 2건** — 마이그 계보(단일 선형 헤드, 골드 생성 리비전이 조상)·Sync 당일 affinity 드리프트(일별 행 회전으로 매일 재생성, 무효화 시 보존 설계 붕괴). 2라운드 연속 신규 클래스 없음 → 수렴. 전체 회귀 백엔드 18스위트 184 assertion green + tsc 0 에러.
- **후속** — 빈 pref/persona 행 자격 정밀화(초미세 모집단·스캔 비용 미미). 설명 TTL(`explained_at`) 도입 검토 — 프롬프트 진화·장기 잔존 일괄 바운드용(DDL 승인 필요). Sync 결정론 폴백 문구(현재 미표시). invalidation 테스트 CASE 단일 조건 케이스 보강. SP-4 — AI 상담실 UX 본가 승격(자기모델 가시화·"나도 몰랐던 나" 카드).

## 2026-07-01 — SP-0: 다이렉트 찬스 개인화 연결 + profile 하이드레이션 근본 수정
- **무엇** — (1) 프론트 Chance 탭이 인증 없는 제네릭 `/api/chance/opportunities`(전 사용자 동일)만 호출해, 매시간 배치로 계산·저장되던 사용자별 매칭(`user_chance_matches`)이 화면에 전혀 노출되지 않던 배선 누락 수정 — 로그인+매칭 존재 시 적합도 순 매칭 우선, 신규·배치 전·비로그인은 제네릭 폴백, 가시화 문구 추가. (2) **근본 원인 수정**: Codex 리뷰가 `profile?.id` 게이트를 지적 → 검증 결과 `setProfile` 호출부가 코드 전체에 0개라 store `profile`이 영영 null, 그래서 `profile?.id`로 게이트된 `useSyncScores`·`useChanceMatches`가 로그인 사용자에게도 항상 비활성(Sync는 "로그인하세요", Chance는 제네릭)이던 공유 버그. `MainLayout`이 이미 부르던 `getCurrentUser()` 결과를 store `setProfile`로 하이드레이션해 해소.
- **왜** — "Sync/Chance에 개인화가 안 보인다"는 사용자 진단의 실제 뿌리. Phase 2 개인화가 백엔드에만 존재하고 UI 게이트가 절대 열리지 않던 상태(설계 의도 아님). 토큰 게이팅(Codex 제안) 대신 공유 root cause를 고쳐 Chance·기존 Sync를 함께 활성화.
- **어디** — [dashboard.ts](../../../../www.yeotaeho.kr/src/lib/api/dashboard.ts)(`fetchMatches`·`ChanceMatchLive` opportunity_id→id) · [useDashboard.ts](../../../../www.yeotaeho.kr/src/hooks/useDashboard.ts)(`useChanceMatches`) · [DashboardView.tsx](../../../../www.yeotaeho.kr/src/components/features/dashboard/DashboardView.tsx)(`ChancePanel` 매칭 우선+폴백) · [MainLayout.tsx](../../../../www.yeotaeho.kr/src/components/layout/MainLayout.tsx)(`setProfile` 하이드레이션·미인증 시 `clearProfile`). 백엔드 무변경(`/api/chance/matches`·`/api/oauth/me` 재사용).
- **검증** — `tsc --noEmit` 0 에러(2회). Codex 리뷰: 1차 P2(profile 미채움) → 근본 수정 → **재리뷰 클린**("Chance matches wiring과 profile 하이드레이션이 기존 인증 API 패턴과 일치"). 커밋 b374f15(Chance)·a70b195(하이드레이션). 완전 시각 검증은 백엔드+로그인 필요 → tsc+Codex+기존 인증 패턴 재사용으로 갈음.
- **후속** — 매칭 카드에 `match_score`·`match_reason` 노출은 SP-3(설명 레이어). Sync 신호 희석(코사인 60% vs 공통 트렌드 40%)은 자기모델(SP-1~3)로 강화. profile 하이드레이션은 로그인 이력 있는 세션 대상 — 추천 쿼리 활성화 스모크(실 로그인)는 후속.

## 2026-06-30 — 개인화 Phase 2: 사용자 성향·스펙 임베딩 통합 + 재임베딩 버그 수정
- **무엇** — Phase 1에서 수집한 성향·스펙을 사용자 임베딩·Chance 매칭에 반영. (1) 순수 헬퍼 `user_embed_text.py`(`build_user_embed_text`·`disposition_spec_terms`)가 성향 enum→한국어 라벨 + 스펙(skills/cert/lang/projects) 직렬화. (2) `_FETCH_UNEMBEDDED_USERS` 가 user_preferences·user_personas LEFT JOIN + `GREATEST(updated_at들) > computed_at` 로 재임베딩 트리거 — 기존엔 `e.user_id IS NULL` 만 봐서 데이터 변경 시 재임베딩 안 되던 버그 수정. `embed_users` 는 해시 동일 시 OpenAI 호출 생략(멱등). (3) `chance_match_service` user_terms 에 같은 헬퍼로 성향·스펙 가산.
- **왜** — Sync/Chance 개인화가 직무+키워드만 쓰던 병목 해소. 데모그래픽(나이·성별·지역)은 편향 방지 위해 임베딩·매칭에서 제외(user_profiles 미JOIN).
- **어디** — [user_embed_text.py](../hub/services/user_embed_text.py)(신규 순수 헬퍼) · [embed_repository.py](../hub/repositories/embed_repository.py)(`_FETCH_UNEMBEDDED_USERS`) · [embed_service.py](../hub/services/embed_service.py)(`_user_text` 위임·`embed_users` 해시스킵) · [chance_repository.py](../hub/repositories/chance_repository.py)(`_FETCH_USERS`) · [chance_match_service.py](../hub/services/chance_match_service.py)(user_terms). 스키마 변경 없음.
- **검증** — `scripts/user_embed_text_test.py` 16/16 · `scripts/user_reembed_test.py` 7/7(실 OpenAI 재임베딩 사이클 포함) · `scripts/chance_user_terms_test.py` 6/6 PASS. 회귀 `embed_helpers_test.py` 7/7 · `chance_extract_match_test.py` 21/21. 커밋 aac9972·9f53489·54d2893.
- **후속** — 스케줄러 `_REFINE_PIPELINE` 에서 `chance_match` 가 `user_embed` 보다 먼저 실행 → 데이터 변경 당일 Chance 의미(코사인) 경로 1일 지연(키워드 경로는 즉시·멱등 보정). `user_embed` 를 앞으로 옮기면 해소(별도 결정). 프론트 입력 UI는 Phase 3.

## 2026-06-30 — 시장 전망 수직 신설: TimesFM 14일 예측 (선행 지표)
- **무엇** — `market_insight` 에 Pulse 와 나란한 독립 '시장 전망' 수직 추가. `raw_market_timeseries` 티커별 `close_price`(약 250거래일·29티커)를 **TimesFM 2.5**(google/timesfm-2.5-200m-pytorch, torch 백엔드)로 14일 예측 → 예측 % 수익률로 변환 → 상대 turnover 가중(통화 중립)으로 섹터 집계 → `clamp(round(50 + 5×수익률), 0, 100)` 전망 점수 + 방향 배지(강세/상승/중립/하락/약세 전망) + 분위수 밴드 신뢰도. Pulse 점수는 불변. 무거운 모델(spoke/infra)과 순수 산출(hub/services) 분리 — 핵심 수학은 torch 없이 단위 테스트.
- **왜** — Pulse 는 과거~현재의 열기(활동량)+방향(감성·등락)이고 등락 modifier 마저 전일 대비(과거)다. 제품 핵심 컨셉 "선행 행동 지표"를 강화하려 **미래를 가리키는** 지표가 필요. 건수 축들은 일회성 백필이라 실 시계열이 없고, `raw_market_timeseries` 만이 실 연속 일별 시계열이라 예측 대상. 곱셈 아닌 가산도 동일 이유로 Pulse 와 정합. Phase 0 에서 Python 3.13/torch313 end-to-end 실현가능성 검증(JAX 불필요·`timesfm[torch]==2.0.1`·로드 84s·추론 0.6s·분위수 idx0=mean·1~9=q0.1~q0.9).
- **어디** — [forecast_pipeline.py](../hub/services/forecast_pipeline.py)(순수: 점수·배지·신뢰도·섹터 집계), [timesfm_forecaster.py](../spokes/infra/timesfm_forecaster.py)(모델 래퍼+Forecaster Protocol+순수 헬퍼+FakeForecaster), [forecast_refine_service.py](../hub/services/forecast_refine_service.py)(오케스트레이션), [forecast_repository.py](../hub/repositories/forecast_repository.py)(티커 시계열·멱등 replace·서빙), ORM [refined_market_forecast_silver.py](../models/bases/refined_market_forecast_silver.py)·[market_forecast_log.py](../models/bases/market_forecast_log.py), 마이그레이션 [c8f1a2d3e4b5](../../../alembic/versions/c8f1a2d3e4b5_add_market_forecast_tables.py)(down_revision d1a2b3c4e5f6), [settings.py](../../../core/config/settings.py)(`FORECAST_*` 7필드), [insight_routor.py](../../../api/v1/insight/insight_routor.py)(`GET /api/insight/forecast`·`POST /forecast/refine`), [scheduler.py](../../../core/scheduler.py)(`_job_market_forecast`·`_REFINE_PIPELINE` pulse_refine 직후), [requirements.txt](../../../requirements.txt)(`timesfm[torch]==2.0.1`), 배치 [market_forecast_refine.py](../../../scripts/market_forecast_refine.py). 설계 [MARKET_FORECAST_TIMESFM_DESIGN.md](./MARKET_FORECAST_TIMESFM_DESIGN.md)·계획 [MARKET_FORECAST_TIMESFM_PLAN.md](./MARKET_FORECAST_TIMESFM_PLAN.md).
- **검증** — 순수 [market_forecast_test.py](../../../scripts/market_forecast_test.py) **31 PASS**(수익률→점수·배지 임계·통화중립 USD+KRW·분위수 밴드·음수밴드 가드·빈/미매핑/가중0 행미생성·ORM 메타). 마이그레이션 Neon 적용·두 테이블 존재 확인. FakeForecaster E2E 스모크 `{tickers:29,silver:11,gold:11}` ai-data 65/상승. **실 TimesFM 스모크** `{tickers:29,silver:11,gold:11}` score 37~62 전 섹터 상이(fintech 62 +2.37%·mobility 37 −2.69%, 50+5×ret 정합), conf=0.0 일부는 band_rel≥0.3 정상. SDD(서브에이전트 구동) 8태스크 각 spec+quality 리뷰 통과 + opus 전체 브랜치 최종 리뷰 Fix-then-merge(머지 전 2건 반영). 커밋 0bf680d(plan)..37f400e, Critical/Important 0.
- **후속** — (비차단) ① 11/12 섹터만 시장데이터 보유 — 미보유 섹터 티커 수집 확충. ② `_TICKER_SERIES_SQL` 날짜 윈도잉(데이터 누적 시, max_context=512 정렬). ③ Pulse 시장 modifier 를 본 예측으로 격상(둘 다 미선택). ④ Pulse 점수 자체 예측(일별 Gold 누적 후). ⑤ 별도 Py 워커/컨테이너로 모델 격리(prod 스케일, master MSA 후보와 결). ⑥ `FORECAST_*` env 실사용 후 튜닝. ⑦ E2E 스모크 코드화·`--smoke` 플래그. 라이브: `python main.py`(reload=True)라 코드 자동 반영, 실모델 스모크로 Gold 1회 생성됨.


- **무엇** — ① 텍스트 감성을 전체 관측수-가중 평균(baseline) 대비로 **중심화**(`center_text_sentiment` 순수함수) — 산업 뉴스 LLM 감성의 양수 쏠림을 제거하고 '평균보다 긍정/부정인가'의 상대 변별로 전환(시장 방향은 이미 ±대칭이라 미중심화). ② `sentiment_k`·`shrink_k`·`window`·축 가중·중심화 토글을 `settings.PULSE_*` env 로 노출. ③ 감성 백필 윈도우 30→365일로 확대(전 분류행 감성 완비).
- **왜** — 2차 후 prod 검증에서 텍스트 볼륨↑로 전 섹터 양수 쏠림(상대 변별 약화)이 관측됨 → 중심화로 해소. 실사용 데이터 축적 후 코드 변경 없이 재조정하려면 파라미터를 .env 로 빼야 함. 30일 밖 행은 sentiment NULL 이라 히스토리 차트가 감성 미반영 → 전기간 백필.
- **어디** — [pulse_pipeline.py](../hub/services/pulse_pipeline.py)(`center_text_sentiment`), [pulse_repository.py](../hub/repositories/pulse_repository.py)(`fetch_directional_modifiers(center_text)`), [settings.py](../../../core/config/settings.py)(`pulse_*` 6필드), [pulse_refine_service.py](../hub/services/pulse_refine_service.py)(설정 주입), [sentiment_backfill.py](../../../scripts/sentiment_backfill.py).
- **검증** — [pulse_scoring_test.py](../../../scripts/pulse_scoring_test.py) 62 PASS(중심화 7건 추가). 전기간 백필 +293행(전부 economic, 60~365일 NULL 0 = 완비). refine 재실행(modifiers 2816·gold 2997). 라이브 `GET /api/insight/pulse` 틸트 0 중심 균형 확인(food-agri 90·edutech 73·ai-data 42·energy 43·반도체 35, 상대 변별). reload=True 라 코드 자동 반영.
- **후속** — 중심화는 전기간 단일 baseline(시간 드리프트 미보정) — 필요 시 per-기간 baseline. 축 가중 1:1·`sentiment_k`15·`shrink_k`8·윈도우7은 실사용 후 `PULSE_*` env 로 재조정. 공개 prod 별도 서버면 동일 반영 필요.

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
