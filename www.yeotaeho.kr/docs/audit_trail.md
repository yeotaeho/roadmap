# 프론트엔드 작업 기록 (Audit Trail)

`www.yeotaeho.kr` 프론트엔드 변경 이력. 최신 항목을 맨 위에 추가한다.

## 2026-07-11 — 히어로 마우스 좌표 추종 패럴랙스

- **무엇** — 랜딩 히어로에서 커서 위치를 따라 배경 오브·펄스 라인·콘텐츠가 depth별 반대 방향으로 미세하게 움직이는 마우스 패럴랙스를 추가했다.
- **왜** — 랜딩 완성 후 사용자 요청. 스크롤 연출에 더해 정지 상태에서도 반응하는 동적 히어로.
- **어디** — `src/components/features/landing/sections/HeroSection.tsx` — `gsap.matchMedia` 데스크톱+모션허용 브랜치에서 pointermove→`gsap.quickTo(x/y)` 8세터, `pointerType!=="mouse"` 가드, pointerleave 원위치, 리스너 해제 cleanup 반환. 스크롤 스크럽(yPercent)과 다른 축(x/y px)이라 간섭 없음. 커밋 ef55a26·e243a85.
- **검증** — `pnpm build` 통과. 헤드리스 Edge(playwright-core, 프로덕션 빌드 :3210)로 커서 좌→우 이동 시 orb-a ±38px 동방향·orb-b ∓55px·콘텐츠 ∓12px 역방향, 모바일 폭(≤1023px) 불변 확인. 이중 리뷰 — 1차 code-reviewer COMMENT(MEDIUM 1: 터치스크린 pointerType 미필터 → 반영), 2차 Codex 클린(수명주기·간섭·성능 지적 0).

## 2026-07-11 — 루트 랜딩 페이지 신설 (비로그인 방문자 메인 화면)

- **무엇** — musign.net식 스크롤 인터랙션 랜딩 페이지를 신설하고 루트 `/`를 조건 분기했다 — 게스트=랜딩, 로그인=기존 대시보드 그대로.
- **왜** — 처음 방문한 사용자에게 플랫폼(청년 인사이트)을 설명하는 메인 화면 부재. deepsona.ai·clickme.co.kr류 소개 페이지 + 스크롤 동적 연출 요청.
- **어디**
  - 라우팅 — `src/app/(main)/page.tsx` 삭제 → `src/app/page.tsx`(metadata + `yi-auth-pending` 인라인 스크립트) + `src/components/features/landing/HomeGate.tsx`(3-상태 게이트: SSR/첫렌더=랜딩, 로그인=`<MainLayout><DashboardView/>`, 로그인이력+복원중=BrandSplash)
  - 인증 — `src/store/slices/authSlice.ts`(`isAuthResolved`+`yi-auth-hint`, login/logout/setToken 갱신), `src/components/AuthInitializer.tsx`(`initializeAuth().finally`로 resolved 마킹), `src/store/types.ts`·`src/store/index.ts`
  - 랜딩 — `src/components/features/landing/` 신설: GSAP 3.15+ScrollTrigger+Lenis(랜딩 스코프 한정), 섹션 6종(히어로 텍스트 리빌·Problem 핀+워드 리빌·Stats 카운트업·Features 가로 스크럽 핀·HowItWorks 라인 드로잉·CTA 글로우), 인라인 SVG 비주얼 6종(`visuals/FeatureVisuals.tsx`), 카피 상수 `landing.copy.ts`(텍스트 교체는 이 파일만)
  - 커밋 2d46a9c → 029c6dd(1차 리뷰 반영: 게스트 랜딩 SSR 복원+로그인 이력자 첫 페인트 가림) → 28418f1(2차 리뷰 반영: 섹션 matchMedia cleanup+스플래시 접근성)
- **검증** — `pnpm build` 통과(`pnpm lint`는 Next 16 `next lint` 제거로 기존 파손). 헤드리스 Edge로 SSR HTML 랜딩 본문 포함, 핀 2개·가로 스크럽·카운트업(12/3/365/4)·다크모드·모바일 375px 가로 오버플로 없음·reduced-motion(핀 0·콘텐츠 즉시 표시·Lenis 미마운트)·헤더 스크롤 배경 전환(상/중/하단)·힌트 pending→guest 랜딩 폴백 확인. 이중 리뷰 — 1차 code-reviewer HIGH(랜딩 SSR 부재) 수정, 2차 Codex Important(matchMedia cleanup)·Minor(스플래시 a11y) 반영 후 재리뷰 승인.
- **후속** — 에셋 미보유: `public/og.png`(1200×630), 로고 SVG 라이트/다크 2종, 히어로 배경 영상(선택, ≤4MB 루프), 기능 실스크린샷 6장(1600×1000 WebP — 현재 SVG 목그래픽이 대체). 카피 확정 시 `landing.copy.ts`만 수정.

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
