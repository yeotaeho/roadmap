# ai_coach 작업 기록

## 2026-06-28 — 최소 SSE 멘토 슬라이스(도메인 첫 구현)
- **무엇** — 빈 스텁이던 ai_coach 도메인에 SSE 스트리밍 멘토링 가동. 사용자 페르소나·활성 로드맵·상위 Pulse 섹터를 맥락으로 주입해 OpenAI 응답을 토큰 단위 스트리밍.
- **왜** — Roadmap·페르소나 루프 완성 후 대화형 코치 첫 슬라이스. RAG·FastMCP·인사이트 지갑은 범위에서 분리(다음 슬라이스).
- **어디** — [core/llm/client.py](../../../core/llm/client.py) `stream_chat`(async generator)·`_COACH_SYSTEM_PROMPT`. [coach_repository.py](../hub/repositories/coach_repository.py)(맥락 공유 DB read)·[coach_service.py](../hub/services/coach_service.py)(`build_coach_context` 순수 + `stream_sse` SSE 이벤트). 라우터 [coach_routor.py](../../../api/v1/coach/coach_routor.py) `POST /api/coach/stream`(auth, StreamingResponse `text/event-stream`, `data: {type:delta|done|error}`). 프론트 `www.yeotaeho.kr/src/lib/api/coach.ts`(fetch ReadableStream)·`components/features/coach/CoachView.tsx`(실 스트리밍 연결, mock 제거).
- **검증** — `scripts/coach_stream_test.py` 10/10 PASS(실측 LLM 30 deltas·맥락 주입·done·401), tsc --noEmit 0 에러.
- **후속** — RAG(인사이트 임베딩 검색)·FastMCP 툴·인사이트 지갑(coach_sessions/wallet 테이블). 대화 히스토리 영속화.
