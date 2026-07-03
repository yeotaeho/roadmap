# SP-8 — 상담실 리디자인: 능동 조사 인터뷰 + LangGraph + 메모리 계층 설계

2026-07-04 확정(플랜 모드 승인). 상담실을 "수동 응답 챗"에서 **설문 근거 능동 인터뷰**로 재설계하고, 대화
엔진을 LangGraph(StateGraph + Postgres checkpointer)로 전환하며, 코치가 소비할 메모리 계층을 확정한다.

## 배경 — 실사용 스크린샷에서 드러난 3 문제

1. **역할 침범** — 상담사가 "온라인 강의·블로그 운영" 같은 실행 가이드(코치 영역)를 함.
   `_CONSULT_SYSTEM_PROMPT`가 로드맵 생성만 금지하고 실행 조언은 안 막음.
2. **수동적 조사** — 상담실의 존재 목적이 자기모델(RIASEC·Big Five) 추출인데 사용자가 말을 꺼내야만
   데이터가 쌓이고, 추출도 다음날 10:00 배치라 성향 지도 피드백 루프가 느림.
3. **메모리 전략 부재** — 컨텍스트가 수동 롤링 요약 코드로 관리되고, 향후 코치(ai_coach)가 상담 맥락을
   소비할 저장 전략이 없음.

## 확정 결정 (사용자 확답)

| 결정 | 선택 |
|---|---|
| 대화 주도권 | **하이브리드** — AI가 설문 기반 질문으로 주도, 사용자가 고민을 꺼내면 경청 모드 전환 후 자연 복귀 |
| 조사 완료 처리 | **라운드 완료 + 즉시 추출, 세션 유지** — 완료 판단 시 즉시 추출·지도 갱신, 대화 계속(재개 모델 유지). 일일 10:00 배치는 백스톱 |
| LangGraph | **상담실 전면 도입** — StateGraph + Postgres checkpointer, 세션 id = thread_id (AGENT_ROADMAP §6 정합) |

## A. 메모리 3계층

```
숏텀   — LangGraph state (+ Postgres checkpointer로 내구화)
         : 최근 대화 창·인터뷰 커버리지·모드. 세션 id = thread_id.
미드텀 — consult_sessions.context_summary (세션 롤링 요약, 기존 유지)
롱텀   — user_self_model + user_self_model_evidence (정제층)
         : 코치는 raw 대화가 아니라 이 정제층 + 세션 요약을 읽는다(도메인 결합 방지).
```

- `consult_messages`는 **원문 SSOT 유지**(추출·감사가 읽음). LangGraph state는 작업 맥락만 담아 체크포인트
  비대화를 피한다.
- 체크포인터 테이블은 langgraph 자체 스키마(setup) — **Neon DDL이라 사용자 승인 게이트**.

## B. 하이브리드 능동 인터뷰

- **문항 은행** — SP-4 리서치(워크넷 6축×34문항·O*NET 6축×10~30문항 독립 풀,
  [research](../research/2026-07-03-riasec-scoring-research.md)) 근거로 RIASEC 6축 + Big Five 5축의
  대화형 질문 은행(`consult_interview_bank.py`)을 설계. LLM이 문항을 그대로 읽는 게 아니라 축별 주제
  가이드로 활용해 자연스러운 질문을 생성한다.
- **커버리지 추적** — LangGraph state에 11축 각각의 신호 확보 상태(근거 수·confidence)를 유지 →
  "다음에 뭘 물을지"(미커버 축 우선)와 "라운드 완료"(전 축 신호 확보) 판단 근거.
- **경청 모드** — 사용자가 고민을 꺼내면 조사 중단·경청(모드 state 전환), 마무리되면 미커버 축 질문으로
  자연 복귀. 심문 느낌 방지가 하이브리드의 존재 이유다.
- **완료 → 즉시 추출** — 완료 판단 시 `SelfModelExtractionService.extract_session` 재사용(force —
  MIN_NEW 게이트 우회) → SSE `self_model_updated` 이벤트 → 프론트 성향 지도 즉시 리페치. 일일 배치는
  완료 선언 없이 흘러간 대화의 백스톱으로 유지.

## C. 역할 경계

- **프롬프트 개정** — 실행 가이드(강의·블로그·플랫폼 추천 등) 금지. 필요 시 "그건 로드맵 코치에서
  도와드릴 거예요"로 위임 안내. 자기이해 반영·질문에 집중.
- **민감정보 원칙 개정** — "능동적으로 캐묻지 않음"을 **민감 차원(트라우마·제약)에 한정**. 흥미·업무
  스타일 문항은 능동적으로 묻는다. `DATA_COLLECTION_SOURCES_GUIDE_V3.md` §8 갱신.

## D. SP 분해 (순서대로, 각각 스펙 상세화→플랜→SDD)

### SP-8a — LangGraph 전환 (동작 동등 게이트)
행동 변화 없이 엔진만 교체 — 회귀 판단이 쉬운 순수 전환.
- `ConsultService` 내부를 StateGraph로: `load_context → (조건)summarize → respond(스트리밍)` 노드.
  AsyncPostgresSaver(체크포인터), 세션 id=thread_id.
- 어댑터 경계: LangGraph 런타임은 `user_intelligence/spokes/`(infra)에, `ConsultService`는 얇은 어댑터.
- 기존 SSE 계약(delta/done/error)·`consult_messages` 저장·`context_summary` 요약 동작 유지.
- **Task 0 = PoC**: `langgraph-checkpoint-postgres` 설치(현재 미설치 — 체크포인터는 psycopg 기반이라
  asyncpg 스택과 별도 커넥션, Neon 호환 검증 필수) + `astream_events`→SSE delta 재매핑 검증.
  현 설치: langgraph 1.1.10 · langchain-openai 1.2.1.
- 게이트: 기존 consult 테스트 스위트 무수정 green.

### SP-8b — 하이브리드 능동 인터뷰 + 즉시 추출
- 인터뷰 state(축별 커버리지·모드)·문항 은행·시스템 프롬프트 전면 개정(조사 주도+경청 전환+실행 가이드
  금지+민감 캐묻기 금지).
- 라운드 완료 판단 → `extract_session(force=True)` 즉시 호출 → SSE `self_model_updated` → 프론트
  `["self-model", id]` 무효화·리페치.
- 문서: §8 원칙 개정. 프론트: ConsultView SSE 이벤트 처리·SelfModelPanel 리페치.

### SP-8c — 코치 공유 메모리 인터페이스 (소형)
- 롱텀 읽기 서비스(자기모델 + 최근 세션 요약 N개) 계약 정의 — ai_coach가 나중에 소비. 코치 미구현이므로
  인터페이스·테스트만(YAGNI).

## E. 리스크

- AsyncPostgresSaver(psycopg) + Neon 호환 — SP-8a Task 0 PoC로 선검증. 실패 시 폴백: 자체 JSONB
  체크포인터(consult_sessions 확장) 또는 MemorySaver+기존 DB 재구성 하이브리드.
- 체크포인터 테이블 DDL — Neon 쓰기라 사용자 승인 게이트.
- 첫 토큰 지연 — 그래프 노드 최소(3~4개)·얕은 루프 유지.
- 조사 라운드 완료 즉시 추출 LLM 비용 — 라운드당 1회라 일일 배치와 큰 차이 없음.

## F. 검증

- SP-8a: 기존 consult 테스트 스위트 무수정 green(동작 동등) + 그래프 단위 테스트 + PoC 스크립트.
- SP-8b: FakeLLM으로 커버리지 추적·모드 전환·완료→추출→SSE 통합 테스트, `pnpm exec tsc --noEmit` 0.
- 각 SP: 이중 리뷰(code-reviewer → Codex) + 감사기록 + main 병합 — 기존 SP 사이클 동일.

## 파일 지도 (전체 조망)

| 영역 | 파일 |
|---|---|
| 엔진(어댑터화) | `backend/domain/user_intelligence/hub/services/consult_service.py` |
| LangGraph 런타임 | `backend/domain/user_intelligence/spokes/`(신설 — 그래프·체크포인터) |
| 조립→노드 이관 | `backend/domain/user_intelligence/hub/services/consult_context.py` |
| 프롬프트 | `backend/core/llm/client.py`(`_CONSULT_SYSTEM_PROMPT`) |
| 즉시 추출 | `backend/domain/user_intelligence/hub/services/self_model_extraction_service.py`(force) |
| 문항 은행 | `backend/domain/user_intelligence/hub/services/consult_interview_bank.py`(신설, SP-8b) |
| 프론트 | `www.yeotaeho.kr/src/components/features/consult/ConsultView.tsx`·`SelfModelPanel.tsx` |
| 재사용(무변경) | `SelfModelService`(blend·merge)·`blend_axes`·추출 파서 |
