# market_insight 작업 기록 (Audit Trail)

최신 항목을 맨 위에 추가(역순). 형식은 `CLAUDE.md` [작업 기록 규칙](../../../../CLAUDE.md) 참고.

---

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
