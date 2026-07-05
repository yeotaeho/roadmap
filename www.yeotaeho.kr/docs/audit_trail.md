# 프론트엔드 작업 기록 (Audit Trail)

`www.yeotaeho.kr` 프론트엔드 변경 이력. 최신 항목을 맨 위에 추가한다.

## 2026-07-05 — 앱-셸 좌측 사이드바 도입 (인사이트·로드맵·상담·코치)

- **무엇** — 상단 Header는 전체 폭 유지하고 그 아래를 `[좌측 full-height 사이드바 | MainTabBar→콘텐츠→Footer]` flex 셸로 재구성했다. 대시보드(인사이트)는 상단 탭을 좌측 사이드바(펄스 접기/펴기 + 8개 세부 섹션)로, 로드맵은 상단 서브탭(여정 개요·성장 아카이브)을 좌측 사이드바로 옮겼다. 상담실·코치는 레이아웃 일관성용 정적 사이드바 틀을 추가했다. 사이드바와 콘텐츠 상태는 페이지별 Context로 공유한다.
- **왜** — 인사이트 대시보드에 좌측 네비게이션을 도입한 뒤 나머지 세 탭도 같은 앱-셸 형태로 통일해 달라는 요구였다. 페이지 사이드바가 MainTabBar 왼쪽에 서려면 전역 셸(MainLayout) 재구성과 상태 공유가 필요했다. full-bleed 방식은 가로 스크롤바를 유발해 flex 셸로 대체했다.
- **어디**
  - 공통 셸 — `src/components/layout/MainLayout.tsx` (라우트별 사이드바+Provider 렌더·`shell()` 헬퍼), `src/components/layout/SideNav.tsx` (사이드바 컨테이너·버튼 공유)
  - 대시보드 — `src/components/features/dashboard/DashboardNavContext.tsx`, `DashboardSidebar.tsx`, `DashboardView.tsx`, `PulseTab.tsx`(section prop)
  - 로드맵 — `src/components/features/roadmap/RoadmapNavContext.tsx`, `RoadmapSidebar.tsx`, `RoadmapView.tsx`
  - 상담·코치 — `src/components/features/consult/ConsultSidebar.tsx`, `src/components/features/coach/CoachSidebar.tsx`
- **검증** — `npx tsc --noEmit` clean 통과. 이중 리뷰 통과 — 1차 code-reviewer APPROVE(Critical/Important 0·Minor 6 중 3건 반영), 2차 Codex 기능적 결함 없음. 브라우저 육안 검증은 dev 서버가 Turbopack `.next/dev/lock`을 점유해 관리형 프리뷰 불가, HMR로 확인했다.
- **후속** — 상담실은 단일 채팅이라 사이드바 1항목(틀), 코치는 플레이스홀더라 실제 콘텐츠·섹션이 생기면 사이드바 항목을 확장한다. 남은 Minor — `PULSE_SECTIONS`에 `satisfies` 추가(선택), `/roadmap`·`/consult` 하위 라우트 추가 시 라우트 매칭을 `startsWith`로 넓혀 Provider 밖 렌더를 방지한다.
