# SP-9 — 상담실 자기모델 배경 기억 반영 + 인터뷰 진행 가시화 설계

2026-07-04 확정. 상담실 3공백 중 ①·②를 구현한다(③ 로컬 즉시 추출은 Docker/Linux 전환으로 해소됨).
후속 과제 기록: [consult_followups.md](../../domain/user_intelligence/docs/consult_followups.md).

## 배경

실사용 검토에서 드러난 상담실 공백 — ①상담사가 파악한 성향을 대화에 안 씀(페르소나+섹터만 주입) ②인터뷰
진행·완료가 사용자에게 안 보임(조용히 패널만 리페치). ③(로컬 즉시 추출 불능)은 Windows 체크포인터
fail-open이 원인이었고, backend 도커화(Linux 컨테이너)로 체크포인터가 정상 동작함을 실증해 해소됐다.

## ① 자기모델 배경 기억 주입 (톤 확정 — 숨은 배경 기억)

- **데이터 흐름**: `_load_context_system`이 매 턴 `SelfModelService(db).get_self_model(user_id, include_sensitive=False)`를
  추가로 읽어 `self_model_memory()` 직렬화 블록을 시스템 프롬프트에 append(읽기 실패 시 조용히 생략, 기존 맥락과 동일).
- **직렬화 `self_model_memory(model: dict | None) -> str`** (user_intelligence 도메인 내, market_insight 미import):
  **신호 있는 축만** — 흥미(`riasec.top_codes` 짧은 라벨)·성격(Big Five 뚜렷한 축만 강점/중립 서술어, 신경성=정서안정성)
  ·`narrativeSummary`. 셋 다 없으면 빈 문자열 → 블록 미주입(초기 all-50 노이즈 방지).
- **프롬프트 지침 한 문장**(`_CONSULT_SYSTEM_PROMPT`): "'지금까지 파악한 당신'은 잠정적 배경 기억이다. 단정하지
  말고(발견 과정 유지), 이미 파악된 축은 다시 캐묻지 말며, 더 깊은 질문·개인화에만 활용하라."
- **경계**: 자기모델 읽기 전용·민감 근거 미주입. SP-8c 계약과 정합(상담사도 raw 대화 아닌 정제층을 읽음).

## ② 인터뷰 진행률·완료 가시화

**결정**(사용자 확답): 진행률 = **성향 지도 패널 헤더 슬림 바**("성향 파악 N/11" + 게이지), 완료 = **패널 상태
변화 + 배지**("성향이 정리됐어요 ✨"). 진행률 소스 = **커버리지 SSE**(라이브·Linux/prod 정상).

**데이터 흐름**
```
plan 노드(consult_graph): 커버리지 갱신 후
   writer({"type":"coverage", "covered":N, "total":11})           ← 턴마다 SSE(additive)
extract 노드: 완료 시 self_model_updated (기존)
        ↓
consult.ts streamConsult: onCoverage(covered, total) 콜백 추가(onSelfModelUpdated 옆, 선택 파라미터)
        ↓
ConsultView → 상담 페이지 상태(or 작은 store) → SelfModelPanel 로 coverage 전달
        ↓
SelfModelPanel 헤더: "성향 파악 N/11" + 슬림 게이지 바
완료(self_model_updated 리페치): 패널 채움 + "성향이 정리됐어요 ✨" 배지(완료 상태)
```
- **SSE additive** — 기존 `delta`/`done`/`error`/`self_model_updated` 불변, `coverage` 추가(프론트 구파서 무시).
- `covered` = `sum(1 for a in ALL_AXES if coverage.get(a))`, `total = len(ALL_AXES)`(11). plan 노드가 `get_stream_writer()`로 방출.
- `SelfModelPanel`은 현재 props 없이 `useQuery`로 자체 조회 → coverage prop(`{covered,total}|null`) 추가.

## 경계·검증

- **Windows 로컬 한계(명시)**: 체크포인터 fail-open이라 커버리지가 턴마다 리셋 → 바가 낮게/이번 턴만 표시.
  **라이브 e2e는 Docker/Linux**(체크포인터 정상, SP-8 도커 검증). 로컬은 유닛/서비스 테스트로 로직 검증.
- **테스트**: ① 순수 `self_model_memory`(신호 게이팅·정서안정성·빈 모델→빈 문자열)·`_load_context_system`이 자기모델 블록 주입(FakeService). ② plan 노드 coverage 이벤트 방출(그래프 테스트)·기존 consult 스위트 회귀. 프론트 `pnpm exec tsc --noEmit` 0.
- **범위 밖**: ③(해결), 규준 백분위, 커버리지 DB 영속(무체크포인터 폴백 — 별도 후속).

## 분해 (SP-9)

- **Task 1 — ① 백엔드**: `self_model_memory` 직렬화 + `_load_context_system` 주입 + 프롬프트 지침. 순수·서비스 테스트.
- **Task 2 — ② 백엔드**: plan 노드 `coverage` SSE 이벤트. 그래프 테스트.
- **Task 3 — ② 프론트**: `consult.ts` onCoverage·`ConsultView` 상태 전달·`SelfModelPanel` 헤더 바·완료 배지. tsc.

## 파일 지도

| 영역 | 파일 |
|---|---|
| ① 직렬화·주입 | `backend/domain/user_intelligence/hub/services/consult_service.py`(`self_model_memory`·`_load_context_system`) · `backend/core/llm/client.py`(`_CONSULT_SYSTEM_PROMPT`) |
| ② 백엔드 이벤트 | `backend/domain/user_intelligence/spokes/infra/consult_graph.py`(plan 노드) |
| ② 프론트 | `www.yeotaeho.kr/src/lib/api/consult.ts` · `components/features/consult/ConsultView.tsx` · `SelfModelPanel.tsx` |
| 재사용(무변경) | `SelfModelService.get_self_model` · `consult_interview_bank.ALL_AXES` |
