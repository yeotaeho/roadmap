# market_insight 작업 기록 (Audit Trail)

최신 항목을 맨 위에 추가(역순). 형식은 `CLAUDE.md` [작업 기록 규칙](../../../../CLAUDE.md) 참고.

---

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
