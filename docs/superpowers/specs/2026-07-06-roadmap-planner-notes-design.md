# Roadmap 플래너(WBS)·노트 설계

- **날짜**: 2026-07-06
- **상태**: 사용자 승인 완료 (브레인스토밍 5문답 + 섹션별 승인)
- **범위**: Roadmap 탭에 플래너(백로그·스프린트·주간 타임라인)와 노트(마크다운+링크) 탭 신설 — 풀스택 수직 슬라이스

## 1. 배경과 목표

현재 Roadmap 탭은 여정 지도(퀘스트 트리)와 성장 아카이브(월별 달력+일별 로그) 2탭이다. 퀘스트 트리는 장기 방향만 제시하고 실행 계층이 없다. 이번 작업으로 다음을 추가한다.

1. **플래너(WBS)** — 퀘스트를 실행 가능한 태스크로 분해(AI 또는 수동)해 백로그에 쌓고, 스프린트로 묶어 주간 타임라인에서 일정을 본다.
2. **노트** — 옵시디언식 `[[링크]]`를 지원하는 마크다운 메모 공간. 태스크·퀘스트에 연결 가능.

레퍼런스 톤: 다크/라이트 대시보드 이미지 4종 (월간 캘린더형 work.time, 주간 간트형 Shipper's, 시간표형 Meetings, 카드 그리드형). 채택 뷰는 **보드 + 주간 간트**.

### 확정된 요구 (브레인스토밍 문답)

| 질문 | 결정 |
|---|---|
| 탭 배치 | 기존 2탭 유지 + 플래너·노트 탭 추가 (총 4탭) |
| AI-퀘스트 관계 | 퀘스트 → 백로그 분해 (태스크 완료가 퀘스트 진행률로 노출) |
| 플래너 뷰 | 백로그+스프린트 보드, 주간 타임라인(간트) 2종 |
| 노트 깊이 | 마크다운 노트 + `[[링크]]` + 백링크 + 태스크/퀘스트 연결 |
| 구현 범위 | 풀스택 수직 슬라이스 (테이블+API+UI 한 번에) |
| 접근 방식 | A안 — hrowth_journey 도메인 자체 확장, 간트 CSS Grid 자체 구현, dnd-kit + react-markdown만 추가 |

기존 독립 `task` 도메인은 재사용하지 않는다 (bounded context 경계 유지).

## 2. 데이터 모델 — 새 테이블 3개 (Alembic 마이그레이션 1개)

### `planner_sprints`

| 컬럼 | 타입 | 비고 |
|---|---|---|
| id | BigInt PK | |
| user_id | UUID | 인덱스 |
| title | String | 예: "1주차 — CS 기초" |
| goal | Text nullable | 스프린트 목표 한 줄 |
| start_date / end_date | Date | 간트 표시 범위 |
| state | String | `planned` / `active` / `done` |
| position | Integer | 보드 컬럼 정렬 |
| created_at / updated_at | timestamptz | |

### `planner_tasks`

| 컬럼 | 타입 | 비고 |
|---|---|---|
| id | BigInt PK | |
| user_id | UUID | 인덱스 |
| sprint_id | BigInt FK nullable | **NULL = 백로그** (백로그 별도 테이블 없음) |
| quest_key | String nullable | 퀘스트 느슨한 참조 — 로드맵 재생성 시 태스크 보존, dangling 허용 |
| title | String | |
| description | Text nullable | |
| status | String | `todo` / `doing` / `done` |
| start_date / due_date | Date nullable | 간트 bar 범위. 백로그 항목은 비워둠 |
| estimated_days | Integer nullable | 예상 소요 일수 — AI 분해 결과·카드 표시·날짜 부여 시 due_date 프리필 |
| position | Integer | 컬럼 내 드래그 순서 |
| source | String | `user` / `ai` — AI 분해 출처 배지 |
| created_at / updated_at | timestamptz | |

### `roadmap_notes`

| 컬럼 | 타입 | 비고 |
|---|---|---|
| id | BigInt PK | |
| user_id | UUID | |
| title | String | **unique(user_id, title)** — `[[제목]]` 해석 기준 |
| content | Text | 마크다운 원문 |
| linked_titles | JSONB | 저장 시 `[[...]]` 파싱 캐시 → 백링크 조회 |
| task_id | BigInt nullable | 태스크 연결 (선택) |
| quest_key | String nullable | 퀘스트 연결 (선택) |
| created_at / updated_at | timestamptz | |

### 퀘스트 연동 원칙

태스크 전부 `done`이어도 퀘스트 상태를 자동 전이하지 않는다. 여정 지도에서 "연결 태스크 n/m 완료" 진행률 배지만 표시한다 (로드맵 재생성과의 충돌 배제, YAGNI).

## 3. API — 기존 `/api/v1/roadmap` 라우터 확장 (인증 의존성 재사용)

```
GET    /roadmap/planner              # 보드 전체: sprints[] + tasks[] 1회 로드
POST   /roadmap/planner/sprints
PATCH  /roadmap/planner/sprints/{id} # 제목·기간·상태 부분 수정
DELETE /roadmap/planner/sprints/{id} # 소속 태스크는 백로그로 복귀(sprint_id NULL)
POST   /roadmap/planner/tasks        # 수동 생성
PATCH  /roadmap/planner/tasks/{id}   # 이동(sprint_id·position)·상태·일정 부분 수정
DELETE /roadmap/planner/tasks/{id}
POST   /roadmap/planner/decompose    # {quest_key} → LLM 3~6개 태스크 분해 → 백로그 insert
GET    /roadmap/notes                # 목록: id·title·updated_at·본문 1줄 미리보기
GET    /roadmap/notes/{id}           # 본문 + 백링크 목록
POST   /roadmap/notes
PUT    /roadmap/notes/{id}           # 저장 시 [[..]] 재파싱
DELETE /roadmap/notes/{id}
```

- **decompose**: `roadmap_planner_service.py` 패턴 — LLM json_object 호출, 퀘스트(제목·설명·난이도) + 페르소나·target_job 컨텍스트. 실패·키 미설정 시 난이도별 결정론 템플릿 폴백. 같은 퀘스트 재분해는 서버에서 막지 않고 프론트에서 "이미 n개 분해됨" 경고만.
- 서비스 신설: `planner_service.py`, `note_service.py`. 리포지토리는 기존 `roadmap_repository.py` 패턴으로 별도 파일.

## 4. 프론트엔드

### 탭 구조

`RoadmapSidebar` 4탭: 여정 지도 | 플래너(신설) | 노트(신설) | 성장 아카이브. `RoadmapNavContext` 탭 타입에 `planner`/`notes` 추가. 기존 컴포넌트 수정은 여정 지도의 "연결 태스크 n/m" 배지 추가뿐.

### 플래너 탭 (`PlannerTab.tsx`) — 서브 토글 `[ 보드 | 타임라인 ]`

**보드 뷰**
- 좌측 고정 컬럼 = 백로그: 태스크 카드(제목·퀘스트 칩[난이도색 emerald/amber/violet]·AI 배지·예상 기간) + 퀘스트별 그룹 헤더 + "＋ 태스크".
- 우측 = 스프린트 컬럼 가로 스크롤: 헤더에 제목·기간·진행률 바, "＋ 스프린트".
- **dnd-kit** 드래그: 백로그 ↔ 스프린트, 컬럼 내 순서. 드롭 → `PATCH tasks/{id}` 낙관적 업데이트 (TanStack Query onMutate 롤백).
- 백로그 상단: 퀘스트 선택 → "AI로 분해" 버튼 (indigo-600, 로딩 스피너, 완료 시 새 카드 하이라이트 — Framer Motion).

**타임라인 뷰** (주간 간트, CSS Grid 자체 구현)
- 7열 그리드, 헤더 요일+날짜, 오늘 컬럼 하이라이트, `◀ 오늘 ▶` 주 이동.
- `start_date~due_date` 태스크를 pastel bar(`grid-column: span n`)로 표시 — 제목 + "n days". 색상은 스프린트별 순환 팔레트(sky/emerald/violet/rose — 라이트 100번대 bg, 다크 900번대 bg).
- 스프린트 기간은 배경 음영 밴드.
- **MVP 제외**: bar 드래그-리사이즈 → bar 클릭 팝오버에서 날짜·상태 수정. (후속 과제)
- 날짜 없는 태스크는 우측 "일정 미정 n건" 미니 패널 → 클릭해 날짜 부여.

### 노트 탭 (`NotesTab.tsx`)

- 2단 `lg:grid-cols-[280px_1fr]`. 좌측: 검색 + "＋ 새 노트" + 목록(제목·수정일·미리보기 1줄).
- 우측: 제목 인풋 + 편집(textarea 모노스페이스)/미리보기(`react-markdown`) 토글.
- `[[` 입력 시 제목 자동완성 드롭다운. 미리보기의 `[[제목]]`은 내부 링크 — 없는 제목은 점선 스타일, 클릭 시 생성 제안.
- 하단 백링크 섹션 "이 노트를 언급한 노트 n개".
- 저장: 명시적 버튼 + `Ctrl+S`. (자동저장 디바운스는 후속)
- 태스크/퀘스트 연결 칩 — 연결 시 태스크 카드에 노트 아이콘 표시.

### Mock 폴백

비로그인 시 read-only 샘플 데이터 (`src/data/plannerMock.ts` 신설) — JourneyMapTab 기존 컨벤션과 동일. 편집 시도는 로그인 유도.

### 신규 의존성 (2개)

`@dnd-kit/core` + `@dnd-kit/sortable`, `react-markdown`. 설치 전 React 19 호환 확인.

### 스타일 컨벤션

기존 유지: `rounded-2xl border shadow-sm bg-white dark:bg-slate-800`, indigo-600 primary, `dark:` 전면 지원, Framer Motion 0.2s 전환.

## 5. 테스트·검증

- **백엔드 pytest**: `[[..]]` 파싱·백링크 조회, 태스크 이동(sprint_id/position), 스프린트 삭제 시 태스크 백로그 복귀, decompose LLM 폴백 경로.
- **프론트**: `pnpm test` 기존 스위트 통과 + Claude Preview 라이브 검증 (보드 드래그·타임라인 렌더·노트 링크) 스크린샷 증빙.
- **커밋 단위**: ① 마이그레이션+ORM 모델 ② 서비스+API ③ 플래너 UI ④ 노트 UI ⑤ AI 분해. 각 단위 커밋 후 이중 리뷰(code-reviewer → Codex) 절차 준수.

## 6. 후속 과제 (이번 범위 제외)

- 타임라인 bar 드래그-리사이즈로 날짜 조정
- 노트 자동저장 디바운스
- 월간 캘린더 뷰 (성장 아카이브와 역할 중복 — 필요성 재검토 후)
- 스프린트 회고(완료 스프린트 요약) 및 성장 아카이브 연동
