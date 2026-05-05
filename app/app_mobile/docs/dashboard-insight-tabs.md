# 인사이트 대시보드 & 메인 도메인 탭 — 디자인·개발 가이드

**대시보드(`DashboardPage`) L2 네 탭**뿐 아니라 메인 바에 나란히 올라가는 **AI 상담(`/consult`) · 전략 로드맵(`/roadmap`) · AI 코치(`/coach`)** 까지, 색상·레이아웃·상태·데이터 소스·웹 매핑을 한곳에서 대조할 수 있게 정리한 문서입니다.  
파일 경로는 모두 `lib/` 기준으로 `app_mobile` 프로젝트 루트를 가리킵니다.

### 목차(빠른 점프)

| § | 내용 |
|---|------|
| 1 ~ 5 | 인사이트 대시보드 L2 탭 요약 및 데이터 레이어 |
| **6 ~ 10** | **메인 라우팅 + AI 상담 / 로드맵 / 코치 상세 스펙** |
| **11** | **통합 변경 체크리스트** |

---

## 1. 대시보드(L1 인사이트) 전체 구조

| 항목 | 내용 |
|------|------|
| 엔트리 | `features/dashboard/presentation/dashboard_page.dart` |
| IA | L2 4탭: **펄스** → **블루오션** → **싱크** → **찬스** (순서 고정) |
| 탭 UI | `AppBar` + `TabBar`(`isScrollable: true`, `TabAlignment.start`) + `TabBarView` |
| 공통 데이터 | `features/dashboard/data/dashboard_mock_data.dart` (`DashboardMockData`) |
| 색 토큰 | `core/theme/app_colors.dart` (`AppColors`) |

### 1.1 하위 네비게이션(스택)

`GoRouter`에서 `/` 대시보드 **자식 경로**로 정의되어 있으며, 루트 네비게이터로 푸시됩니다.

| 경로 | 화면 | 비고 |
|------|------|------|
| `/pulse/sectors/:slug` | `SectorDetailPage` | 펄스 분야 상세 |
| `/gap/issues/:issueId` | `GapIssueDetailPage` | 블루오션 이슈 상세 |
| `/chance/opportunities/:opportunityId` | `ChanceDetailPage` | 찬스 기회 상세 |

---

## 2. 공통 디자인 토큰 (`AppColors`)

| 토큰 | Hex(참고) | 용도 |
|------|-----------|------|
| `indigo600` | `#4F46E5` | 테마 보조 강조, 칩 선택 등 |
| `indigo700` | `#4338CA` | 보조 인디고 |
| **`sectorMetricAccent`** | **`#6366F1`** | **분야 지표 통일색** — 펄스·블루오션·찬스에서 스코어·뱃지·게이지 채움·CTA 등에 사용 |
| `slate50` ~ `slate950` | — | 슬레이트 스케일(배경·서피스 계열과 조합) |
| **`syncChanceCardSurface`** | **`#333F50`** | **싱크·찬스 탭 카드 면** — 페이지 베경과 구분되는 네이비 카드 배경 |
| `gaugeTrackForAccent(Color accent)` | — | **게이지 미채움 트랙** — `slate900` 베이스에 액센트를 소량 블렌드. 채움색과 카드 배경이 섞여 보이지 않게 함 |

### 2.1 지표 색 통일 원칙

- **채움·숫자·뱃지 글자**: 한 카드 안에서는 동일 액센트(`sectorMetricAccent` 또는 `PulseSectorCard.accent` — 현재 목 데이터에서는 **전 분야 `sectorMetricAccent`와 동일**).
- **트랙(미채움)**: 액센트와 **같은 색이 아님** — `gaugeTrackForAccent`로 어둡게 처리.

---

## 3. 데이터 레이어 요약 (`DashboardMockData`)

개발 시 “어디를 고치면 화면이 바뀌는지” 빠르게 찾기 위한 매핑입니다.

| 영역 | 주요 식별자 | 설명 |
|------|-------------|------|
| 펄스 히어로 | `pulseHero` | 속도·주차 등 히어로 카드 |
| 펄스 분야 | `pulseSectors` | `PulseSectorCard`: `slug`, `title`, `score`, `status`, **`accent`** |
| 펄스 상세 | `pulseDetailBySlug` | `slug` → `PulseSectorDetail` |
| 블루오션 칩 라벨 | `gapSectorChipLabels` | 슬러그 → 짧은 한글 라벨 (상단 `ChoiceChip`) |
| 블루오션 카드 | `gapIssues`, `gapIssuesForSector` | `GapIssueCard`: `id`, **`sectorId`** (= `pulseSectors[].slug`), `problem`, `chance` |
| 블루오션 상세 | `gapDetailById` | `id` → `GapIssueDetail` |
| 싱크 | `syncOverview` | 싱크로율 점수· 증감· 근거 문구 등 |
| 찬스 | `chanceCards`, `chanceDetailById` | 리스트 카드 · 상세 |

---

## 4. 탭별 상세

### 4.1 펄스 (`PulseTab`)

| 항목 | 내용 |
|------|------|
| 파일 | `features/dashboard/presentation/tabs/pulse_tab.dart` |
| 스크롤 | 단일 `ListView`, 좌우 패딩 `16` |
| 의존성 | `fl_chart`, `go_router`, `DashboardMockData`, `AppColors` |

#### 섹션 순서(위→아래)

1. `_PulseHero` — 글로벌 펄스 히어로(그라데이션·속도 등)
2. `_LiveKeywordTicker` — 라이브 키워드 티커
3. **분야별 트렌드 속도** — `pulseSectors` → `_RichSectorCard` ×6 (세로 리스트)
4. `_CausalChainCards` — 인과관계 체인
5. **3줄 경제 브리핑** — `_BriefingThreeLines`, `_BriefingCarousel`
6. `_CrossoverSection` — 세대교체·크로스오버
7. `_PulseChartDeck` — 모멘텀·관심 비중(차트 덱)
8. `_RisingKeywordCloud` — 급상승 키워드 클라우드
9. `_LiveKeywordTicker` 반복
10. `FilledButton.tonalIcon` → **`/coach`** (“AI 코치에게 이 흐름 물어보기”)

#### 분야 카드 (`_RichSectorCard`)

- **배경**: `ColorScheme.surfaceContainerLow` · alpha `0.9`
- **액센트**: `sector.accent` (= 목 데이터상 **`AppColors.sectorMetricAccent` 통일**)
- **구성**: 제목 + 우측 점수, 상태 뱃지 + “모멘텀 N%”(퍼센트만 액센트), `LinearProgressIndicator`(트랙 `gaugeTrackForAccent`), 하단 “상세 · 근거 · 키워드”
- **탭 동작**: `context.push('/pulse/sectors/${s.slug}')`

#### 차트·도넛 등

- 모멘텀 비중 도넛(`_ShareDonutChart`) 등은 조각 색을 **인디고 계열 팔레트**로 구분(첫 색 `sectorMetricAccent` 등).

---

### 4.2 블루오션 (`GapTab`)

| 항목 | 내용 |
|------|------|
| 파일 | `features/dashboard/presentation/tabs/gap_tab.dart` |
| 상태 | `StatefulWidget` — **`_sectorFilter`** (`String?`, `null` = 전체) |
| 스크롤 | `CustomScrollView` + **고정 헤더** `SliverPersistentHeader(pinned: true)` |

#### 레이아웃

1. 상단 안내 문구 (`SliverToBoxAdapter`)
2. **분야 칩 바** — “전체” + `pulseSectors` 6개 (`gapSectorChipLabels`로 칩 짧은 라벨)
3. 필터된 `gapIssuesForSector` → `_GapVerticalCard` 리스트 (`SliverList.separated`)

#### 카드 (`_GapVerticalCard`)

- **배경**: `surfaceContainerLow` · alpha `0.9` (펄스 분야 카드와 동일 계열)
- **상단**: `sectorBySlug(card.sectorId)`로 펄스와 동일 메타(제목·점수·상태 뱃지·모멘텀·선형 게이지)
- **본문**: “결핍” / “기회” + `FilledButton`(액센트 배경) → `context.push('/gap/issues/${card.id}')`

#### 개발 시 유의

- 새 이슈 추가 시 **`sectorId`** 는 반드시 `pulseSectors[].slug` 중 하나와 일치.
- `gapDetailById`에 같은 `id`의 상세가 있어야 상세 페이지가 성립.

---

### 4.3 싱크 (`SyncTab`)

| 항목 | 내용 |
|------|------|
| 파일 | `features/dashboard/presentation/tabs/sync_tab.dart` |
| 스크롤 | `ListView`, 패딩 `16` |

#### 레이아웃

1. **카드 1장** — `syncOverview`
   - **카드 배경**: **`AppColors.syncChanceCardSurface`** (`#333F50`)
   - 원형 `CircularProgressIndicator` + 중앙 점수·전주 대비
   - 상단 트렌드 칩(`Chip`) · 하단 `keywordEvidence`
2. “왜 이렇게 나왔나요?” — `reasonLines` 불릿
3. `OutlinedButton` → **`/consult`**

#### 색

- 게이지: 테마 `primary` / 트랙 `outlineVariant`(alpha) — 카드 면은 고정 네이비 토큰.

---

### 4.4 찬스 (`ChanceTab`)

| 항목 | 내용 |
|------|------|
| 파일 | `features/dashboard/presentation/tabs/chance_tab.dart` |
| 스크롤 | 세로 `ListView`, 카드 간격 `12` |

#### 레이아웃

- 안내 문구 1줄
- `chanceCards` → **`_ChanceCard`** 세로 나열 (가로 캐러셀 없음)

#### 카드 (`_ChanceCard`)

- **배경**: **`AppColors.syncChanceCardSurface`**
- **액센트**: **`AppColors.sectorMetricAccent`** (뱃지·모멘텀 %·선형 게이지·매칭 행·`FilledButton`)
- **타이포**: 제목 **흰색**, 보조 **`#94A3B8`** (로컬 `_mutedOnCard`), 모멘텀 라벨/숫자 분리 스타일
- **동선**: `context.push('/chance/opportunities/${o.id}')`

---

## 5. 파일 빠른 참조

| 역할 | 경로 |
|------|------|
| 대시보드 셸 | `features/dashboard/presentation/dashboard_page.dart` |
| 펄스 | `features/dashboard/presentation/tabs/pulse_tab.dart` |
| 블루오션 | `features/dashboard/presentation/tabs/gap_tab.dart` |
| 싱크 | `features/dashboard/presentation/tabs/sync_tab.dart` |
| 찬스 | `features/dashboard/presentation/tabs/chance_tab.dart` |
| 목 데이터 | `features/dashboard/data/dashboard_mock_data.dart` |
| 색 토큰 | `core/theme/app_colors.dart` |
| 라우터 | `core/router/app_router.dart` |

---

## 6. 메인 탭 라우팅과 웹 매핑

`StatefulShellRoute.indexedStack` 으로 L1 네 브랜치를 유지하며 **URL은 Next.js 메인 네비와 동일**합니다.

| 순서(index) | 경로 | `pageBuilder` 위젯 | 웹 레퍼런스(대략) |
|-------------|------|-------------------|-------------------|
| 0 | `/` | `DashboardPage` | 인사이트 대시보드 본문 |
| 1 | `/consult` | `ConsultPage` | `consult/page.tsx`, Deep Discovery |
| 2 | `/roadmap` | `RoadmapPage` | `roadmap/page.tsx`, `RoadmapView` |
| 3 | `/coach` | `CoachPage` | `coach/page.tsx`, `CoachView` |

추출 화면(대시보드 하위 스택만 루트 네비): `pulse/sectors/:slug`, `gap/issues/:issueId`, `chance/opportunities/:opportunityId` — `app_router.dart` 의 `parentNavigatorKey: rootNavigatorKey` 패턴 참고.

**공통 톤(상담·로드맵·코치)**: 셀 배경 `AppColors.slate950`, 카드 면은 `slate800`/`slate900` 위주로 **웹 트레이딩/다크 터미널** 계열 정렬. 대시보드는 기본 `Theme` Scaffold를 오래 썼다면 명도 대비 차이만 인지하면 됨.

---

## 7. AI 상담 탭 (`ConsultPage`)

| 항목 | 내용 |
|------|------|
| 진입 파일 | `features/consult/presentation/consult_page.dart` |
| 웹 레퍼런스 | `www.yeotaeho.kr/src/app/(main)/consult/page.tsx` 계열 IA |
| 상태 | `_ConsultPageState` — `_phase`, `_dialogStep`, `_messages`, `_quickReplies`, `_keywords` 로 데모 시나리오 분기 |

### 7.1 레이아웃(유사 트레이 스택)

구조는 **상단 카드 블록 + 하단 채 영역(Column)** 과 유사하게 읽히도록 구성되어 있습니다.

```
Scaffold(background: slate950)
├─ AppBar (slate950)
│    ├─ title: 「AI 상담실」 + Deep Discovery(인디고) + 한 줄 부제
│    └─ actions: _LiveAnalysisGoalOrb ──→ showModalBottomSheet (라이브 분석)
└─ body: Column
     ├─ Expanded → ListView
     │    ├─ _LiveProgressCard (LIVE RESULT, sync 배지, 단계 프로그레스, ①②③ 라벨)
     │    ├─ 세션 배지行 (모노스페이스, 가로 스크롤 가능한 Container)
     │    ├─ 「INTERACTIVE · 메시지 피드」+ turn_index 뱃지
     │    └─ 메시지들 _MessageBubble (ai/user/system 카드 패턴 차별화)
     └─ SafeArea 래핑 입력 박스
          ├─ (조건부) 가로 스크롤 Quick Reply ActionChip 행
          └─ Row: TextField + IconButton.filled 전송 + 한 줄 안내 라벨
```

- **메시지 스크롤**: `_scroll.animateTo(maxScrollExtent)` 로 전송 후 하단 고정 패턴.

### 7.2 색·브랜드

| 요소 | 토큰/색 |
|------|---------|
| 셀 배경 | `AppColors.slate950` |
| 카드 면/`LIVE RESULT` 카드 | `slate800` + `Border.all(slate700)` |
| 프로그레스 채움 | 그라데이션 인디고 → 틸(웹 레이더 톤) |
| 틸 액센트(예: ⚡ 줄) | 지역 `_ConsultUi.tealSync` (`0xFF34D399`) |
| 앱바 라이브 오브 | 흰 원 + 인디고 글로우 + 번개 아이콘, 라벨 `라이브`/`분석` |

### 7.3 `_LiveAnalysisGoalOrb`(AppBar 우측)

- **파일 내 private** 상태 위젯, **상담 전용**(코치 월렛 오브와 위젯은 별개).
- **Idle**: `AnimationController.repeat(reverse)` + 스케일 `1.0↔1.045`.
- **탭 시**: `HapticFeedback.lightImpact`, `_waveRing` 확장 테두리 링, `_pressBounce` TweenSequence+`elasticOut` 복귀.
- **Ripple**: `InkWell`(인디고 `splashColor` / `sectorMetricAccent` `highlightColor`, `InkRipple`, `radius: 34`).
- **시트 내용**: `showModalBottomSheet` + `DraggableScrollableSheet` 에 레이더·키워드·요약 등(동일 파일 상단 빌더 메서드 참고).

### 7.4 메시지·입력 규약

| 역할 | 위젯/메모 |
|------|-----------|
| AI 시스템 배너 | `_MessageBubble` system — 인디고 링 라운드 캡슐 |
| 사용자 | 우측 `indigo600` 버블 · 반경 18/6/18/18 |
| AI 일반·카드 | 좌측 `slate800` 버블 또는 헤더+본문 카드 |
| 입력 잠금 | `_inputLocked`(가치관 1턴 등) 일 때 칩 우선 안내 후 전송 허용 |

### 7.5 연동 라우팅

- 기능상 링크는 주로 같은 앱 안 — 스낵바/CTA 에서 다른 탭 진입 필요 시 `go_router` 의 `context.go('/roadmap')` 등과 조합 가능(현 버전에서는 화면 내비에 따라 상이).

---

## 8. 전략 로드맵 탭 (`RoadmapPage`)

| 항목 | 내용 |
|------|------|
| 진입 파일 | `features/roadmap/presentation/roadmap_page.dart` |
| 공유 데이터 | `features/roadmap/data/roadmap_quest_map.dart` ← 웹 `src/data/roadmapQuestMap.ts` 거울 |
| 웹 레퍼런스 | `RoadmapView` / `JourneyMapTab` / `GrowthArchiveTab` |

### 8.1 IA

| L2 서브 탭 | 위젯 | 비고 |
|------------|------|------|
| 여정 개요 | `_JourneyMapBody` | 스킬 트라이앵글 · 키워드 브릿지 · 재귀 `_QuestTreeCard` · `_NextActionsSection` |
| 성장 아카이브 | `_GrowthArchiveBody` | 월 캘린더 그리드 · 일별 로그(TextField)·퀘스트 체크박스 · `archiveActivitySeed` 시드 |

- **탭 헤더 UI**: `TabController` + `TabBarView` 에 동기화되는 **커스텀 두 칸 필** `_RoadmapSubTabBar`(인디고 하단 라인 활성 상태).

### 8.2 색·서피스

| 구역 | 스타일 |
|------|--------|
| `Scaffold`/AppBar | `slate950` |
| 카드 블록 | `slate800`/`slate900` 테두리 `slate700` |
| 키워드 브릿지 칩 | `indigo600` 알파 채우·테두리 + 굵은 인디고 텍스트 |
| 퀘스트 상태 카드 테두리 | `start` 인디고 강조, `done` 에메랄드, `active` 인디고 링, `locked` 투명도↓ |
| 난이도 뱃지 | 입문=에메랄드 계열 · 중급=앰버 · 심화=바이올렛(웹 DIFFICULTY_RING 대응) |

### 8.3 데이터 스키마(요약)

- `skillTriangle`, `bridgeKeywords`, `questTree`(재귀 `QuestTreeNode`) — 변경 시 웹 `.ts` 와 문자열까지 동기 권장.
- `flattenQuestTitles` 로 아카이브 체크박스 제목 플랫 리스트 생성.
- `DayLog`: `completedQuestIds` + `note`, 맵 `_logs` 상태에 로컬 병합 (`archiveActivitySeed` 클론으로 초기화).

### 8.4 캘린더 구현 참고

- **첫 요일 일요일** 정렬은 `weekday % 7` 패턴(JS `getDay()` 와 호환 목적).
- 선택일 변경 시 노트 입력은 **`TextEditingController`** 를 날짜 전환 때마다 `_selectDay` 로 동기화(리빌드마다 새 컨트롤러 만들지 않기).

### 8.5 다음 액션 칩 → 라우팅

- `_NextActionChip` → `GoRouter`: `/consult`, `/coach`, `/` (인사이트 대시보드).

---

## 9. AI 코치 탭 (`CoachPage`)

| 항목 | 내용 |
|------|------|
| 진입 파일 | `features/coach/presentation/coach_page.dart` |
| 데모 데이터 | `features/coach/data/coach_context.dart` ← 웹 `coachContext.ts` |
| 웹 레퍼런스 | `CoachView` + `InsightWalletPanel` 동작 패리티 목표 |

### 9.1 레이아웃(AI 상담과 같은 Column 패턴)

```
Scaffold(slate950)
├─ AppBar — 제목 두 줄(AI 코치 / Daily Mentor · …) + actions: _CoachWalletOrb
└─ body: Column
     ├─ Expanded → ListView
     │    ├─ coach · ctx 모노 배지 행(SingleChildScrollView)
     │    ├─ INTERACTIVE 줄 + 번개(teal)+ turn_index≈
     │    ├─ 가로 데모 ActionChip 2종(찬스/로드맵 컨텍스트)
     │    └─ _UserBubble / _AssistantBubble · 로딩 말풍선(선택) · 하단 스크롤 여백 ~80
     └─ 입력 도크 (상담 탭과 동일 패턴)
          ├─ (조건부) 맥락 지시자 Chip / Strip
          ├─ TextField 화이트 텍스트 + slate800 채우
          └─ IconButton.filled 전송 · 한 줄 목업 힌트
```

- **FAB 없음**(웹 데스크탑 패널 = 모바일에선 시트). 상담의 라이브 오브와 같은 **우상단 플로팅 타원 대체** 역할만 AppBar 버튼이 담당.

### 9.2 `_CoachWalletOrb`

- **_LiveAnalysisGoalOrb 와 같은 애니메이션 패키지**(idle 펄스, 바운스, 인디고 링 확장 파동, `HapticFeedback`, `InkWell` ripple).
- 시각 차이: **아이콘** `account_balance_wallet_rounded`, 레이블 **맥락 / 월렛**.
- **`onTap`**: `Insight Wallet` 패널이 들어있는 `_openWalletSheet` (`DraggableScrollableSheet`).
- 바텀시트 내부: **`StatefulBuilder` + 부모 `_wallet`** — 삭제 후 `setModalState` 로 리스트 곧바로 반영.

### 9.3 대화 상태·목업 브레인

- `_messages`: `_CoachMessage`(role/text/code/badge).
- **초깃값**: `_proactiveGreeting`(로드맵 연계 배지 문자열 포함).
- **전송**: 520 ms 지연 후 `_mockReply` — `coachContext` 의 `CoachAttachedContext` 소스 및 키워드 분기가 웹 `mockReply` 와 같은 의도를 유지.
- **코드 답변**: 삽입 문자열 `_pythonSnippet` + 말풍선 우하단 저장 → `_wallet`(제목에 배지 접두).

### 9.4 말풍선 디자인(상담 정렬 기준을 따름)

| 역할 | 스타일 |
|------|--------|
| 사용자 | 우측, `maxWidth≈82%`, `indigo600`, 반경 18/6/18/18, 흰 본문 14sp |
| AI | 좌측, `maxWidth≈88%`, `slate800` 면, Markdown 본문 + 흰/강조, 코드 블록 다크 카드 에메랄드 모노 |
| 저장 | Stack 으로 말풍선 위에 지갑 `InkWell` |

---

## 10. 디자인·패턴 교차표(개발 검수용)

| 관심 영역 | 대시보드 L2 | 상담 | 로드맵 | 코치 |
|-----------|-------------|------|--------|------|
| 셀 배경 | 기본 Scaffold | slate950 | slate950 | slate950 |
| 카드 면 주력 | 펄스/블루: surfaceLow · 싱크/찬스: 고정색 | slate800/900 혼합 | slate800/900 단계 카드 | slate800 말풍선 |
| 악센트 주축 | `sectorMetricAccent`·인디고 | 인디고+틸 하이라이트 | 인디고 | 인디고+틸(INTERACTIVE) |
| 헤더 CTA 타원 버튼 | — | 라이브 분석 오브 | — | 컨텍스트/월렛 오브 |
| 하단 채 패턴 | 해당 탭 CTA별 상이 | Chips+Field+FilledIcon | 해당 없음(tab 본문만) | Field+FilledIcon 동일 패밀리 |
| 시트 패턴 | — | 라이브 분석 | — | Insight Wallet 시트 |

---

## 11. 변경 시 체크리스트(통합 요약)

### 대시보드(L2)

- **펄스·블루오션 지표 색**: `sectorMetricAccent` 또는 `pulseSectors[].accent` — 목 데이터에서 분야별로 바꿀 경우 두 탭이 함께 보이는지 확인.
- **싱크·찬스 카드 배경**: `syncChanceCardSurface`만 수정하면 두 탭 카드 면이 함께 변함.
- **블루오션 필터**: `gapIssues`의 `sectorId` ↔ `pulseSectors.slug` 정합성.
- **찬스 매칭 게이지**: `match`를 0~100으로 두고 `_matchNorm`으로 진행률 표현.

### AI 상담

- **오브 vs 시트**: `_LiveAnalysisGoalOrb` 가 열 이름(`_openLiveAnalysisSheet`)과 중복 기능을 갖지 않게 유지할 것.
- **Overflow**: AppBar는 긴 문자열 줄이거나 `ellipsis`, 세션 줄은 모노+가로 스크롤.
- **`_phase`/`_dialogStep`** 로직 변경 시 프로그레스 퍼센트·키워드 헬퍼 `_pushKeywords` 일관성 검토.

### 로드맵

- **`roadmap_quest_map.dart` 와 웹 `roadmapQuestMap.ts` 문자열 단일 진실**(한쪽만 수정 시 상이 문구 발생).
- **아카이브**: 날짜 키 `YYYY-MM-DD` 포맷, `_noteController` 수명 관리 필수.

### AI 코치

- **`coach_context.dart`**와 웹 `coachContext.ts` 동기화 (`DEMO_ATTACHED_CONTEXTS`, Active Focus 카피 등).
- **전송 활성**：`_input.addListener(setState)` 없으면 `IconButton.filled` disabled 상태가 업데이트되지 않을 수 있음.
- **`_wallet` 상태**가 시트에 반영되어야 한다면 FAB 대신 현재 패턴처럼 **StatefulBuilder 재빌드** 유지 필요.

---

이 문서는 구현이 바뀔 때 **색 토큰(`AppColors`)·목 데이터 필드명·라우트·프라이빗 위젯 접두 규약** 위주로 함께 갱신하는 것을 권장합니다.
