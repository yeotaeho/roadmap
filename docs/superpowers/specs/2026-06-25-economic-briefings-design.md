# economic_briefings (3줄 경제 브리핑) — 설계 (Spec)

> 작성 2026-06-25. market_insight 도메인. PulseTab에 청년 진로 관점 "오늘의 경제 3줄"을 LLM 생성(결정론 폴백)으로 채운다. ERD §6.1 `economic_briefings`(Gold) 신규 마이그레이션. 전략: [PULSE_REMAINING_VERTICALS_STRATEGY.md](../../../backend/docs/PULSE_REMAINING_VERTICALS_STRATEGY.md).

## 0. 목표 & 성공 기준
- `GET /api/insight/briefing` 이 당일(최신일) 3줄을 반환. `POST /api/insight/briefing/refine` 수동 트리거.
- 순수함수 `_parse_briefing`·`template_briefing` 무DB 테스트 `FAIL=0`.
- 일별 잡으로 생성, 멱등(당일 존재 시 스킵). LLM 실패/희소 시 템플릿 폴백으로 빈 화면 없음.
- 프론트 PulseTab BriefingThreeLines 섹션 라이브, `tsc` 통과.

## 1. 데이터 흐름
당일/최근 `raw_economic_data` 헤드라인(top N) + `pulse_metrics_log` 당일 top3 모멘텀 섹터 + 최근 `refined_gap_insights` → context 문자열 → LLM(gpt-4o-mini) 3줄 생성. 실패/키없음 → `template_briefing`(top movers 기반).

## 2. 마이그레이션 (Gold 1테이블, ERD §6.1)
`economic_briefings`: id BIGSERIAL PK, published_date DATE, line_number INT(CHECK 1~3), content VARCHAR(255), trend_icon VARCHAR(20)(UP_RIGHT/DOWN_RIGHT/WAVE), created_at. `UNIQUE(published_date, line_number)` + INDEX(published_date). ORM `EconomicBriefing` → env.py import 추가 → `alembic revision --autogenerate` 검토 → `upgrade head`(prod 승인).

## 3. LLM (core/llm/client.py)
- `_BRIEFING_SYSTEM_PROMPT`: 청년 진로 관점, **정확히 3줄**, 각 ≤40자, 줄별 trend_icon(UP_RIGHT/DOWN_RIGHT/WAVE), 억지생성 금지. JSON `{"lines": [{"content": str, "trend_icon": str}, ...]}`.
- `_parse_briefing(raw) -> list[dict]`(순수): 정확히 3줄·content 비어있지 않음·trend_icon 검증(미지정→WAVE). 3줄 미만/파싱불가 → `[]`(폴백 신호). content 255자 컷.
- `LlmClient.generate_briefing(context) -> list[dict]`.

## 4. 폴백·서비스·리포지토리
- `template_briefing(movers: list[dict]) -> list[dict]`(순수, `briefing_service.py`): top movers로 결정론 3줄(예: "{섹터} 모멘텀 {+x%} — 관련 직무 주목", trend_icon=momentum 부호). movers<3이면 가용분 + 일반 문구로 3줄 채움.
- `BriefingRepository`(`briefing_repository.py`): `fetch_context()`(raw_economic 헤드라인+pulse top movers+gap), `today_exists()`, `upsert_gold(published_date, lines)`(UNIQUE upsert), `fetch_latest()`(서빙: 최신일 3줄).
- `BriefingRefineService.refine_and_serve(force=False)`: force 아니고 today_exists → 스킵. context → LLM(키 있으면) → 3줄이면 사용, 아니면 template_briefing(movers). upsert_gold. 반환 {generated, source: llm|template|skipped}.

## 5. 엔드포인트 (insight_routor.py)
- `GET /insight/briefing` → `{success, briefings:[{line_number, content, trend_icon}], published_date}`.
- `POST /insight/briefing/refine?force=` → BriefingRefineService 트리거.

## 6. 스케줄러
`_job_briefing_refine`(openai 키 없으면 폴백으로 진행) → `_DAILY_JOBS`의 `pulse_refine` 다음에 등록(top movers 신선).

## 7. 프론트 (PulseTab)
`dashboard.ts`: `fetchBriefing()` + `BriefingLine`·`Briefing` 타입. `useDashboard.ts`: `useBriefing()`. `PulseTab.tsx`: 속도계 행 아래 BriefingThreeLines 섹션(3줄 + trend_icon 화살표/물결, PanelStatus).

## 8. 테스트
- `scripts/briefing_test.py`(무DB): `_parse_briefing`(정상 3줄/2줄→[]/잘못된 icon→WAVE/bad json→[]) + `template_briefing`(movers 3개→3줄/movers 0→3줄 일반/부호별 icon). `FAIL=0`.
- `tsc` + 라이브(prod 마이그레이션 적용 + `run_job_now`/POST refine 1회 → GET 검증).

## 9. 비범위
별도 Silver 테이블(refined_briefing_insights) — Gold 단일로 충분. prompt_version 컬럼 — v1 고정, 변경 시 추가. causal_chains·crossover.
