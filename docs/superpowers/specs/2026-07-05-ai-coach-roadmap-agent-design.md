# AI 코치 + 로드맵 딥 에이전트 설계 스펙

- **날짜**: 2026-07-05
- **상태**: 사용자 승인 (브레인스토밍 완료)
- **선행 문서**: `backend/domain/ai_coach/docs/AGENT_ROADMAP.md` (2026-07-01) — tool 계약 초안·메모리 3계층·읽기 계약(§9)의 SSOT. 본 스펙은 그 결정을 계승하되 deepagents 적용 범위를 확정한다.

---

## 1. 배경과 목표

AI 상담실(/consult)은 사용자의 성향(RIASEC·Big Five·서사·근거)을 파악하는 수직으로 완성됐다. 다음 단계는:

- **AI 코치(/coach)** — 파악된 사용자 데이터 + 플랫폼의 시장 데이터(Bronze→Silver→Gold)를 근거로 진로·기회·이행 방법을 판단해주는 대화형 멘토.
- **로드맵(/roadmap)** — 현재 목업 단발 LLM 생성(`RoadmapPlannerService`)을, 시장 조사·기회 수집·퀘스트 설계를 수행하는 딥 에이전트 생성으로 격상.

### 실현 가능성 판단 (조사 결론)

코치가 tool로 조회할 데이터는 이미 라이브 상태로 충분하다.

| 이해도 축 | 데이터 | 상태 |
|---|---|---|
| 세상(시장) | `pulse_metrics_log`(12섹터+TimesFM 전망), `gap_issues`+`issue_evidences`, `causal_chains`, `refined_investment_flows`, `economic_briefings` | 라이브 |
| 기회 | `chance_opportunities` + `user_chance_matches`(사용자별 매칭점수·이유) | 라이브 |
| 사용자 | `user_self_model`(RIASEC·Big Five·서사·axis_confidence/axis_source), `user_self_model_evidence`(민감정보 격리), `sync_scores_daily`, `user_embeddings` | 라이브 |
| 의미 검색 | `document_embeddings`(pgvector HNSW) | 라이브 |
| 역량 온톨로지 | `ncs_competency_master`(NCS L1~L6) | 존재 |

tool 구현은 대부분 기존 repository 함수를 LLM tool로 감싸는 작업이다. 신규 개발이 필요한 것은 웹 검색/크롤링 tool뿐.

## 2. 확정 결정 (브레인스토밍 Q&A)

1. **deepagents 적용 범위 = 하이브리드.** 코치 채팅은 가벼운 LangGraph tool-calling(즉답 SSE), 로드맵 생성·대규모 분석만 deepagents 딥 에이전트. AGENT_ROADMAP.md의 "채팅엔 ReAct" 결정 유지.
2. **딥 에이전트 발주 경로 = 코치 채팅 + /roadmap 탭 양쪽.** 같은 엔드포인트로 수렴. 목업 플래너는 폴백으로 강등.
3. **코치 v1 tool 범위 = 내부 조회 + 웹(web_search/fetch_url).** render_widget은 v2 이연.
4. **딥 에이전트 실행 = SSE 인프로세스.** consult처럼 API 프로세스 내 실행, 진행률 SSE 스트림, LangGraph 체크포인터로 재개. 워커 큐 이전은 v2 후보.
5. **코치 메인 LLM = Claude Sonnet(`claude-sonnet-5`).** consult는 Gemini 2.5 Flash 유지(수직별 모델 분리). 딥 에이전트는 모델 믹스 — 오케스트레이터·`quest_designer`=Sonnet, `market_analyst`·`opportunity_scout`=저렴 모델(Gemini Flash 또는 Haiku).
6. **웹 tool = Tavily(검색) + WaterCrawl(본문 추출).** Naver API 미도입. provider 인터페이스는 플러거블로 유지 — 한국어 로컬 콘텐츠 커버리지가 부족해지면 보조 provider 재도입 가능.
7. **RAG = 구조화 우선, 벡터는 보조.** §4.1 참고.

## 3. 전체 아키텍처

```
┌─ /coach (채팅) ──────────────┐      ┌─ /roadmap (탭) ─────────────┐
│ 코치 채팅 에이전트            │      │ 재생성 버튼                  │
│ LangGraph tool-calling       │      └──────────┬──────────────────┘
│ (consult 패턴 재사용, 즉답)   │                 │
│   └─ launch_roadmap tool ────┼─────────┐       │
└──────────────────────────────┘         ▼       ▼
                                ┌─ 로드맵 딥 에이전트 (deepagents) ──┐
                                │ planning(write_todos) + 서브에이전트│
                                │ SSE 진행률, 체크포인터 재개          │
                                │ 산출 → user_roadmaps/roadmap_quests│
                                └────────────────────────────────────┘
                     둘 다 같은 tool 레이어(내부 DB 조회 + 웹) 공유
```

- tool 레이어는 일반 Python 함수 모듈 `backend/domain/ai_coach/spokes/agents/tools/` — 기존 repository 함수의 얇은 read-only 래퍼. 코치 채팅과 딥 에이전트가 공유.
- "플랫폼 이해도"는 tool이 아닌 **정적 지식 주입**: 6개 탭의 의미·데이터 출처·프론트 라우트를 담은 `platform_context.md`를 코치 시스템 프롬프트에 상시 포함, 딥 에이전트에는 deepagents 가상 파일시스템으로 제공. 프론트 구조는 대화 중 변하지 않으므로 조회 tool 불필요.

## 4. Tool 계약 (공유 레이어)

전부 read-only. 반환은 토큰 절약형 요약 JSON. AGENT_ROADMAP 초안 7종을 확정하고 2종(`get_ncs_competencies`, `launch_roadmap_generation`) 추가.

| tool | 내부 구현 | 비고 |
|---|---|---|
| `get_pulse_trends(sector?)` | `pulse_repository.fetch_overview` / `fetch_history` | TimesFM 전망 포함 |
| `get_gap_issues(sector?, issue_id?)` | `gap_repository.fetch_active_issues` / `fetch_issue_by_id` | 근거 URL 포함 |
| `get_chance_matches(type?)` | `chance_repository.fetch_opportunities` | user별 매칭점수·이유 |
| `get_sync_snapshot()` | `sync_repository.fetch_scores` | 섹터 적합도 상위 |
| `get_user_profile()` | 신규 `ConsultMemoryService.read_for_coach()` | §9 계약 구현. 자기모델 + 비민감 근거 + 최근 상담 요약 |
| `search_insights(query, sector?)` | `document_embeddings` pgvector 유사도 검색 | 쿼리 임베딩은 text-embedding-3-large |
| `get_ncs_competencies(keyword)` | `ncs_competency_master` 조회 | 퀘스트 설계용 (딥 에이전트 위주) |
| `web_search(query)` | **Tavily** — 쿼리 → URL·제목·스니펫 목록 (provider 플러거블 인터페이스) | 출처 URL 필수 반환, `TAVILY_API_KEY` |
| `fetch_url(url)` | **WaterCrawl** scrape — URL → LLM-ready 마크다운 (셀프호스트 이전 여지) | 타임아웃·응답 크기 상한, `WATERCRAWL_API_KEY` |
| `launch_roadmap_generation(focus?)` | 딥 에이전트 잡 핸들 반환 | 코치 채팅 전용 |

### 4.1 RAG 전략 (`search_insights`)

기반: `document_embeddings`(gap_issues·chance_opportunities·refined_innovation_signal 청크, halfvec 3072, HNSW cosine, text-embedding-3-large 고정).

1. **구조화 우선, RAG 보조** — 구조화 tool(Pulse·Gap·Chance·Sync)이 답할 수 있는 질문은 RAG를 쓰지 않는다. RAG는 개방형 의미 질문 전용. 이 라우팅을 코치 시스템 프롬프트에 명시.
2. **검색 파이프라인** — 에이전트 생성 한국어 쿼리 → text-embedding-3-large 임베딩(저장 모델과 일치 필수) → HNSW cosine top-K(K=8) + 필터(`sector_slug`, `source_table`, 최근 90일 기본·에이전트가 확장 가능) → 거리 임계값 컷 → `(source_table, source_id)` dedupe(문서당 최고 청크만).
3. **반환 계약** — 청크 텍스트 + `source_table/source_id` + 섹터. 코치는 이를 인용하고 필요 시 구조화 상세 조회(`get_gap_issues(issue_id)` 등)로 **승격**하는 2단 패턴(벡터로 찾고 → 구조화로 확정). 리니지(`raw_table_ref`)로 원문 출처 링크 제시 가능.
4. **개인화는 벡터로 하지 않음** — `user_embeddings`는 Sync 전용 유지. 코치 개인화는 `read_for_coach()` 구조 주입으로 (설명 가능성·중복 방지).
5. **신선도는 기존 임베딩 배치에 위임** — 코치 쪽 재임베딩 없음, recency 필터만 기본 적용.
6. **v2 여지** — Postgres FTS 하이브리드 + 리랭커. v1 미포함(YAGNI).

## 5. 코치 채팅 에이전트

- **그래프**: `ai_coach/spokes/infra/coach_graph.py` — `prepare → agent(tool loop) → persist`. tool 루프는 LangGraph 표준 tool-calling, 반복 상한 4~5회.
- **세션**: 신규 `coach_sessions` / `coach_messages` 테이블 (consult로 개명해 간 것과 동일 구조로 Alembic 재생성). `thread_id = session_id`, 기존 `get_checkpointer()` 싱글턴 공유 (fail-open 원칙 유지).
- **컨텍스트**: `consult_context.build_llm_messages` 패턴 재사용 + `read_for_coach()` 스냅샷을 시스템 블록으로 주입. 롤링 요약(`context_summary`/`summarized_until`) 동일 패턴.
- **SSE 이벤트**: 기존 `delta`/`done`/`error`에 추가 —
  - `tool_call` {name, label} — "시장 데이터 조회 중…" UI 표시용
  - `tool_result` {name, summary} — 요약만 (원본 페이로드 미노출)
  - `roadmap_job` {job_id} — 딥 에이전트 발주 알림 (프론트가 로드맵 진행 스트림 구독 트리거)
- **LLM**: Claude Sonnet(`claude-sonnet-5`), `langchain-anthropic` 직결 (LangGraph tool-calling 네이티브). `resolve_user_llm`은 건드리지 않고 코치 전용 settings(`COACH_LLM_PROVIDER`/`COACH_LLM_MODEL` + `ANTHROPIC_API_KEY`) 추가. consult는 Gemini 2.5 Flash 유지.
- **API**: `api/v1/coach/coach_routor.py` — consult와 동일 4종 (`POST /coach/sessions`, `POST /coach/stream`, `POST /coach/sessions/{id}/end`, `GET /coach/sessions/{id}/messages`).
- **프론트**: `/coach` 준비중 페이지를 ConsultView 구조를 재사용한 CoachView로 교체. tool 활동 인디케이터 + 발주 시 로드맵 진행 배너. SSE 소비는 기존 `getReader()` 패턴.

## 6. 로드맵 딥 에이전트 (deepagents)

- **의존성**: `deepagents` 패키지 신규 도입 (LangGraph 위에 구축된 하네스 — 기존 체크포인터·스트리밍과 호환).
- **위치**: `hrowth_journey/spokes/agents/roadmap_deep_agent.py` — 산출물(user_roadmaps) 소유 도메인 기준. tool 레이어는 ai_coach 공유 모듈 import.
- **구성**: `create_deep_agent(model, tools=[내부 tool + web], subagents=[...])`
  - 서브에이전트 3종 (deepagents 서브에이전트별 모델 오버라이드 활용 — 비용 최적화):
    - `market_analyst` — Pulse·Gap·causal·전망 종합 → 유망 방향 후보 도출 (저렴 모델)
    - `opportunity_scout` — Chance 매칭 + 웹 검색으로 실행 가능한 기회·요건 수집 (저렴 모델)
    - `quest_designer` — 자기모델·NCS 역량 기반 퀘스트 트리 설계 (Sonnet)
  - 오케스트레이터 모델: Sonnet.
  - 플래닝: 빌트인 `write_todos` — todo 변경을 SSE `progress` 이벤트로 중계.
  - 파일시스템: StateBackend(메모리 내) — 서브에이전트 간 중간 산출물 교환용.
- **산출 계약**: 최종 출력을 기존 `save_roadmap()` 스키마(title·summary·skill_pillars·bridge_keywords·퀘스트 트리)로 구조화 검증 후 저장. 검증 실패·에이전트 실패 시 `template_roadmap()` 폴백 — 사용자는 항상 유효한 로드맵을 받는다.
- **실행**: `POST /roadmap/generate/stream` (SSE 인프로세스). 이벤트: `progress`(todo·서브에이전트 상태) → `done`(roadmap_id) / `error`. 기존 `POST /roadmap/refine`은 이 흐름으로 위임.
- **비용 가드**: recursion_limit·서브에이전트 호출 상한·웹 호출 상한을 settings 값으로 노출.

## 7. 경계·안전 원칙

1. **Bronze 직접 조회 금지** — 코치·딥 에이전트 모두 Silver/Gold + 자기모델 정제층만 접근.
2. **§9 읽기 계약 강제** — `consult_messages` 원문, `is_sensitive=true` 근거는 어떤 tool로도 노출하지 않는다. 강제 지점은 `read_for_coach()` 단일 구현부.
3. **tool 전부 read-only** — 쓰기는 `save_roadmap()` 하나뿐이며 에이전트 루프 밖(산출 검증 후 서비스 코드)에서 실행.
4. **웹 tool 출처 표기** — web_search/fetch_url 반환에 출처 URL 필수, 코치 응답에 출처 표기를 프롬프트로 유도.

## 8. 단계별 구현 계획 (각 단계 = 커밋 + 이중 리뷰 단위)

| 단계 | 내용 | 완료 기준 |
|---|---|---|
| **C-1 코치 채팅 코어** | 내부 tool 6종 + `read_for_coach()` + coach_graph + 세션 테이블 마이그레이션 + SSE 라우터 + 최소 CoachView | 코치가 실데이터 근거로 답변, tool_call 이벤트가 프론트에 표시 |
| **C-2 웹 tool** | web_search/fetch_url + provider 설정 + 출처 표기 | 최신 웹 정보가 출처와 함께 답변에 반영 |
| **R-1 딥 에이전트** | deepagents 도입, 서브에이전트 3종, `/roadmap/generate/stream`, refine 위임, `launch_roadmap_generation` tool, 프론트 진행률 UI | 딥 에이전트 산출이 스키마 검증 통과, /roadmap 탭 렌더, 코치에서 발주 동작 |
| **v2 (이연)** | render_widget, 인사이트 지갑, 워커 큐 이전, 딥 에이전트 장기 메모리 | — |

## 9. 검증 전략

- **pytest** — consult 스위트 패턴 준용: tool 단위(반환 스키마), 그래프 단위(노드 전이·tool 루프 상한), SSE 계약(이벤트 타입·순서), read_for_coach 민감정보 필터.
- **라이브 verify 스크립트** — 실 DB 대상 tool 반환 확인 + Sonnet tool-calling·Tavily/WaterCrawl 실동작 확인 (SP-11 verify 패턴).
- **폴백 경로 테스트** — 딥 에이전트 강제 실패 시 template_roadmap 폴백 동작.

## 10. 리스크

| 리스크 | 대응 |
|---|---|
| Tavily의 한국어 로컬 콘텐츠(국내 커뮤니티·공고 원문) 커버리지 부족 | provider 인터페이스 플러거블 유지 — 필요 시 보조 provider(Naver 등) 재도입 |
| Sonnet 비용 (코치 대화량 증가 시) | 수직별 모델 분리로 consult는 저렴 유지, 딥 에이전트는 서브에이전트 모델 믹스, 사용량 모니터링 |
| WaterCrawl 클라우드 의존 | 셀프호스트 옵션 존재 — 비용·안정성 이슈 시 compose에 추가 |
| 딥 에이전트 토큰 비용·소요 시간 폭주 | recursion_limit·호출 상한 settings, progress 이벤트로 체감 완화 |
| SSE 인프로세스 장기 실행 중 배포/재시작 | 체크포인터 재개 + 폴백 로드맵 보장. 빈도 높아지면 v2에서 워커 큐 이전 |
| deepagents 신규 의존성의 LangGraph 버전 충돌 | 도입 시 기존 consult 스위트 전체 green 확인 후 진행 |
