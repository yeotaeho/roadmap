# AI 상담실 에이전트화 로드맵 (향후 계획)

> **목적** — AI 코치를 "대화형 멘토"에서 **툴 쓰는 상담 에이전트**로 키우기 위한 방향·단계·아키텍처를 기록한다. 지금 당장 구현이 아니라, SP-2a(영속화)·SP-2b(추출) 완료 후 착수할 트랙의 설계 기준이다.
> **작성일** — 2026-07-01. 근거: 사용자 비전 + Codex 아키텍처 상담 + 내부 검토(2026-07-01 세션). 관련: [코치 영속화 spec](../../../docs/superpowers/specs/2026-07-01-coach-session-persistence-design.md)(SP-2a) · [자기모델 spec](../../../docs/superpowers/specs/2026-07-01-ai-coach-self-model-design.md)(SP-2b).

---

## 1. 비전

코치가 대화 중에 사용자를 위해:
- **내부 데이터 제공** — Pulse 트렌드·Sync 적합도·Chance 매칭·self-model을 근거로 답한다.
- **외부 정보 조회** — 사용자가 원하면 웹 검색·URL 크롤링으로 최신 정보를 가져온다(제한적·안전하게).
- **시각화 산출** — 위젯·다이어그램·차트를 툴 출력으로 렌더해 보기 좋게 전달한다.

즉 코치는 진로 방향을 **데이터·근거와 함께 설명하고, 필요하면 스스로 자료를 찾아 시각화하는** 상담 에이전트가 된다.

## 2. 핵심 결정 — 프레임워크

**deepagents 미도입(지금). 가벼운 LangChain `create_agent` / LangGraph ReAct 에이전트 채택.**

| | deepagents | LangGraph `create_agent`(선택) |
|---|---|---|
| 성격 | 장기·복합 자동화 하니스(파일시스템·서브에이전트·todo·오프로딩) | 얕은 agent loop + 필요한 middleware만 |
| 상담 UI 적합성 | 과함 — 실시간 대화·SSE에 불필요한 표면, DDD 경계 흐림 | 적합 — 명시적 툴 + 얕은 루프 |
| 컨텍스트 관리 | 파일 오프로딩(우리는 DB 영속화라 불필요) | `SummarizationMiddleware` + DB 롤링 요약 |
| 채택 시점 | **미래** "진로 리서치 리포트 생성" 같은 백그라운드 장기 작업 | **이 트랙** 실시간 상담 에이전트 |

> **왜** — 상담실 핵심은 안정적 대화·내부 데이터 조회·제한된 웹 검색·시각화 artifact다. 서브에이전트/파일시스템/planner보다 **명시적 도구 + 얕은 agent loop**가 맞다. deepagents는 첫 토큰 지연·비용·의존성 표면·권한 모델을 상담 도메인에 끌고 와 모듈러 모놀리스의 책임 경계를 흐린다. (Codex·내부 검토 수렴.)

## 3. 단계 (phasing)

1. **[SP-2a] 대화 영속화 + 롤링 요약** — `coach_sessions`/`coach_messages`, 멀티턴 기억, `context_summary` 롤링 요약. (에이전트와 무관한 토대.)
2. **[SP-2b] 세션 후 자기모델 추출** — 종료 세션 → 비동기 추출 → `SelfModelService`. **대화 중엔 self-model을 읽기 전용 컨텍스트로만** 쓰고, 갱신은 감사 가능한 별도 job으로 분리(에이전트 툴이 즉석 갱신하지 않음).
3. **[Agent-1] Tool contract 정의(에이전트 프레임워크와 무관하게 먼저)** — §4의 툴 시그니처·입출력 스키마 확정. 툴 결과는 자연어가 아니라 **typed artifact**.
4. **[Agent-2] SSE artifact 스키마** — §5의 이벤트 타입 도입. UI가 `widget` 이벤트로 차트/다이어그램 렌더.
5. **[Agent-3] 에이전트 어댑터** — `CoachService` 뒤에 `create_agent`/LangGraph ReAct 에이전트를 어댑터로 결합. **DB 세션 id = LangGraph `thread_id`** 매핑. 스트리밍을 §5 스키마로 재매핑.
6. **[Agent-4] 웹 검색/크롤링** — allowlist·rate limit·citation·timeout·content sanitization을 넣고 **제한적으로** 개방.
7. **[Future] deepagents** — "진로 리서치 리포트", "여러 채용·시장 자료 장시간 조사·요약", "백그라운드 agent task" 같은 별도 기능에서 재검토.

## 4. Tool contract (초안 — Agent-1에서 확정)

읽기·idempotent 우선, write 툴은 감사 로그 필수(프로젝트 MCP 원칙과 정합).

| 툴 | 성격 | 반환(typed artifact) |
|---|---|---|
| `get_pulse_trends(sector?)` | 내부·read | 섹터 트렌드 점수·모멘텀 |
| `get_sync_snapshot()` | 내부·read | 사용자 섹터 적합도 상위 |
| `get_chance_matches()` | 내부·read | 사용자 맞춤 공고 매칭 |
| `get_self_model()` | 내부·read | 구조 축(비민감) + 근거 요약 |
| `web_search(query)` | 외부·read | 결과 목록 + 출처(citation) |
| `fetch_url(url)` | 외부·read | 정제 본문 + 출처(allowlist·sanitize) |
| `render_widget(spec)` | 산출 | 위젯/차트/다이어그램 스펙(UI 렌더) |

## 5. SSE 이벤트 스키마 진화

현재: `data: {type: delta|done|error}`. 에이전트화 후 확장:

- `token` — LLM 토큰(기존 delta)
- `tool_call` — 툴 호출 시작(이름·인자 요약)
- `tool_result` — 툴 결과 요약(또는 참조)
- `widget` — 시각화 산출 스펙(UI가 렌더)
- `final` — 최종 응답 완료
- `error` — 오류

> deepagents는 서브에이전트/nested stream까지 들어와 UI 이벤트 설계가 더 복잡해진다 — 가벼운 에이전트를 쓰는 또 하나의 이유.

## 6. 아키텍처 원칙

- **어댑터 경계** — 에이전트 런타임은 `ai_coach/spokes/`(infra)에 두고, `hub/services/CoachService`가 얇은 어댑터로 호출. 도메인 로직이 프레임워크에 종속되지 않게.
- **세션 = thread** — DB `coach_sessions.id`를 LangGraph `thread_id`로 매핑(checkpointer 쓰면 정합).
- **self-model 읽기 전용** — 대화 중 self-model은 컨텍스트로만. 갱신은 SP-2b 비동기 파이프라인(감사 가능).
- **컨텍스트 관리** — DB 원본 메시지 + 세션별 롤링 요약 + 최근 N턴 + self-model 스냅샷 + 필요한 내부 데이터 툴 결과. 장기 기억은 대화 로그가 아니라 self-model 계층에 축적.

## 7. 리스크·가드레일

- **웹 툴** — allowlist·rate limit·citation·timeout·content sanitization 필수. 미설정 시 비활성(fail-closed).
- **지연·비용** — planner/서브에이전트/요약/크롤이 붙으면 첫 토큰 지연↑. 얕은 루프 유지·툴 최소화로 관리.
- **보안** — 웹에서 가져온 콘텐츠를 프롬프트 인젝션 방어 후 사용. write 툴은 감사 로그.
- **MSA 후보** — 대화량·LLM 비용·SSE 집중 시 `ai_coach`는 CLAUDE.md의 MSA 분리 1순위.

## 8. 미해결
- 에이전트 프레임워크 최종 선택(`langchain.create_agent` vs 직접 LangGraph `StateGraph`) — Agent-3 착수 시 PoC로 확정.
- `render_widget` 스펙 포맷(기존 visualize 위젯 규약 재사용 여부).
- 웹 검색 provider·크롤러 선택 및 비용 모델.
