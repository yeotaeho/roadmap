# 선택적 사용자 데이터 개인화 — Phase 3(프론트/온보딩) 구현 플랜

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Phase 1/2에서 만든 선택적 사용자 데이터(기본정보·성향·스펙·관심)를 프로필 페이지의 선택 섹션 + 완성도 미터로 입력받고, 로그인 후 1회 `/onboarding`으로 유도하며(건너뛰기 가능), 관심키워드 풀을 12섹터+직무군으로 재설계한다.

**Architecture:** 자기완결형 섹션 컴포넌트(각자 own draft + 인증 PUT API로 self-save, 기존 PersonaForm 패턴)를 프로필과 온보딩에서 동일하게 재사용한다. 신규 `lib/api/{profile,preferences}.ts` + 훅이 Phase 1 API(`/api/user/profile`·`/api/preferences`)에 배선된다. 로그인 라우팅은 3 OAuth 콜백이 공용 `onboardingTarget()` 유틸을 거치게 한다. 백엔드 변경 없음.

**Tech Stack:** Next.js(App Router)/React 19 · TypeScript · TanStack Query · Zustand · Tailwind + 기존 shadcn/ui(`components/ui/`: Card·Badge·Progress·Tabs) · axios apiClient(토큰 자동주입).

## Global Constraints

- 새 소스 파일 첫 줄: 한 줄 한국어 주석으로 역할 명시. 한국어 문장 종결 `.` `?` `!` 만.
- 검증 게이트 = `pnpm exec tsc --noEmit` 0 에러(프로젝트 관행 — 프론트엔드는 unit test 프레임워크 없음). 가능하면 preview로 시각 확인(베스트 에포트).
- 모든 입력 **선택·nullable**. 미입력은 저장하지 않음(빈값 그대로). 회원가입 필수 폼(직무+키워드, OAuth 전)·기존 OAuth 콜백 토큰 처리 로직은 변경하지 않는다(라우팅 분기만 추가).
- 인증 PUT API만 사용(토큰 보유 상태). 온보딩은 **로그인 후** 1회 — 가입 직후(토큰 없음)가 아님.
- API 응답 계약(Phase 1, 권위 있음):
  - `/api/user/profile`: `{success, profile:{birthYear:number|null, gender, region, currentStatus, educationLevel, source}}`. PUT body `{birthYear?, gender?, region?, currentStatus?, educationLevel?}`.
  - `/api/preferences`: `{success, preferences:{workStyle, companySizePref, workTypePref, workValues:string[], source}}`. PUT body `{workStyle?, companySizePref?, workTypePref?, workValues?}`.
  - `/api/persona`: 기존 + `certifications/languages/links/projects` 배열. PUT 동일.
  - `/api/user/sync-profile`: `{userId, targetJob, interestKeywords:string[]}`. PUT `{targetJob?, interestKeywords}`.
- enum 값(백엔드 고정): gender `male|female|other`; currentStatus `student|job_seeking|employed|career_switch`; educationLevel `high_school|undergrad|bachelor|master|phd`; workStyle `stability|challenge|balanced`; companySizePref `startup|sme|large|public`; workTypePref `office|remote|hybrid`; workValues `growth|work_life_balance|autonomy|impact|compensation`.
- 기존 톤 유지: 미니멀, 성향 enum은 칩/세그먼트 버튼(택1·다중), PersonaForm `inputCls`(`w-full px-3 py-2 border border-gray-300 rounded-md ... focus:ring-red-500`) 스타일 답습. 완성도 미터는 `components/ui/progress`.
- 커밋은 태스크마다. 무관 변경 묶지 않기.

---

### Task 1: API 클라이언트·훅·타입 + 라벨/키워드 상수

**Files:**
- Create: `src/lib/api/profile.ts`
- Create: `src/lib/api/preferences.ts`
- Modify: `src/lib/api/persona.ts` (스펙 4필드 타입·EMPTY 확장)
- Create: `src/hooks/useProfile.ts`
- Create: `src/hooks/usePreferences.ts`
- Modify: `src/hooks/usePersona.ts` (필요 시 무변경 — 타입만 확장되면 됨)
- Create: `src/data/personalizationOptions.ts` (enum→한국어 라벨 + 관심 키워드 풀)

**Interfaces (produces):**
- `fetchProfile(): Promise<BasicProfile>`, `upsertProfile(p: Partial<BasicProfile>): Promise<BasicProfile>` + `useProfile()`/`useUpsertProfile()`.
- `fetchPreferences(): Promise<Preferences>`, `upsertPreferences(p): Promise<Preferences>` + `usePreferences()`/`useUpsertPreferences()`.
- `persona.ts`에 `CertificationItem/LanguageItem/LinkItem/ProjectItem` 타입 + `Persona`에 배열 필드.
- `personalizationOptions.ts`: `GENDER_OPTIONS`·`CURRENT_STATUS_OPTIONS`·`EDUCATION_OPTIONS`·`WORK_STYLE_OPTIONS`·`COMPANY_SIZE_OPTIONS`·`WORK_TYPE_OPTIONS`·`WORK_VALUE_OPTIONS`(각 `{value,label}[]`) + `INTEREST_SECTORS`·`JOB_FAMILIES`(`{value,label}[]`, label=한국어 저장값).

- [ ] **Step 1: `personalizationOptions.ts` 작성**

`src/data/personalizationOptions.ts`:

```typescript
// 개인화 선택 입력 옵션 — enum 한국어 라벨 + 관심 키워드 풀(12섹터+직무군)

export interface Option { value: string; label: string; }

export const GENDER_OPTIONS: Option[] = [
  { value: "male", label: "남성" },
  { value: "female", label: "여성" },
  { value: "other", label: "기타" },
];

export const CURRENT_STATUS_OPTIONS: Option[] = [
  { value: "student", label: "학생" },
  { value: "job_seeking", label: "구직 중" },
  { value: "employed", label: "재직 중" },
  { value: "career_switch", label: "전환 준비" },
];

export const EDUCATION_OPTIONS: Option[] = [
  { value: "high_school", label: "고졸" },
  { value: "undergrad", label: "대학 재학" },
  { value: "bachelor", label: "학사" },
  { value: "master", label: "석사" },
  { value: "phd", label: "박사" },
];

export const WORK_STYLE_OPTIONS: Option[] = [
  { value: "stability", label: "안정 지향" },
  { value: "challenge", label: "도전 지향" },
  { value: "balanced", label: "균형" },
];

export const COMPANY_SIZE_OPTIONS: Option[] = [
  { value: "startup", label: "스타트업" },
  { value: "sme", label: "중소기업" },
  { value: "large", label: "대기업" },
  { value: "public", label: "공공기관" },
];

export const WORK_TYPE_OPTIONS: Option[] = [
  { value: "office", label: "사무실" },
  { value: "remote", label: "원격" },
  { value: "hybrid", label: "하이브리드" },
];

export const WORK_VALUE_OPTIONS: Option[] = [
  { value: "growth", label: "성장" },
  { value: "work_life_balance", label: "워라밸" },
  { value: "autonomy", label: "자율성" },
  { value: "impact", label: "사회적 임팩트" },
  { value: "compensation", label: "보상" },
];

// 관심 분야 — 라벨이 곧 저장값(interest_keywords). 백엔드 Pulse 12섹터와 정렬.
export const INTEREST_SECTORS: Option[] = [
  { value: "AI·데이터", label: "AI·데이터" },
  { value: "반도체", label: "반도체" },
  { value: "바이오·헬스", label: "바이오·헬스" },
  { value: "에너지·기후", label: "에너지·기후" },
  { value: "식품·농업", label: "식품·농업" },
  { value: "핀테크", label: "핀테크" },
  { value: "모빌리티", label: "모빌리티" },
  { value: "콘텐츠·크리에이터", label: "콘텐츠·크리에이터" },
  { value: "에듀테크", label: "에듀테크" },
  { value: "뷰티·패션", label: "뷰티·패션" },
  { value: "물류", label: "물류" },
  { value: "사회서비스", label: "사회서비스" },
];

export const JOB_FAMILIES: Option[] = [
  { value: "엔지니어링", label: "엔지니어링" },
  { value: "데이터·AI", label: "데이터·AI" },
  { value: "기획·PM", label: "기획·PM" },
  { value: "디자인", label: "디자인" },
  { value: "마케팅·영업", label: "마케팅·영업" },
  { value: "연구개발", label: "연구개발" },
  { value: "운영·CS", label: "운영·CS" },
];
```

- [ ] **Step 2: `lib/api/profile.ts` 작성**

`src/lib/api/profile.ts`:

```typescript
// 기본정보(데모그래픽) API — /api/user/profile 조회·저장

import { apiClient } from "./client";

export interface BasicProfile {
  birthYear: number | null;
  gender: string | null;
  region: string | null;
  currentStatus: string | null;
  educationLevel: string | null;
  source?: string | null;
}

const EMPTY: BasicProfile = {
  birthYear: null,
  gender: null,
  region: null,
  currentStatus: null,
  educationLevel: null,
  source: null,
};

export async function fetchProfile(): Promise<BasicProfile> {
  const { data } = await apiClient.get("/api/user/profile");
  return { ...EMPTY, ...(data?.profile ?? {}) };
}

export async function upsertProfile(payload: Partial<BasicProfile>): Promise<BasicProfile> {
  const { data } = await apiClient.put("/api/user/profile", payload);
  return { ...EMPTY, ...(data?.profile ?? {}) };
}
```

- [ ] **Step 3: `lib/api/preferences.ts` 작성**

`src/lib/api/preferences.ts`:

```typescript
// 성향·선호(disposition) API — /api/preferences 조회·저장

import { apiClient } from "./client";

export interface Preferences {
  workStyle: string | null;
  companySizePref: string | null;
  workTypePref: string | null;
  workValues: string[];
  source?: string | null;
}

const EMPTY: Preferences = {
  workStyle: null,
  companySizePref: null,
  workTypePref: null,
  workValues: [],
  source: null,
};

export async function fetchPreferences(): Promise<Preferences> {
  const { data } = await apiClient.get("/api/preferences");
  return { ...EMPTY, ...(data?.preferences ?? {}) };
}

export async function upsertPreferences(payload: Partial<Preferences>): Promise<Preferences> {
  const { data } = await apiClient.put("/api/preferences", payload);
  return { ...EMPTY, ...(data?.preferences ?? {}) };
}
```

- [ ] **Step 4: `persona.ts` 스펙 4필드 확장**

`src/lib/api/persona.ts` 에 타입 추가(기존 SkillItem 등 옆):

```typescript
export interface CertificationItem { name: string; issuer: string; year: string; }
export interface LanguageItem { language: string; test: string; score: string; }
export interface LinkItem { type: string; url: string; }
export interface ProjectItem { title: string; description: string; role: string; period: string; tech_stack: string[]; }
```

`Persona` 인터페이스와 `PersonaUpsert`(있으면)·`EMPTY` 상수에 4필드 추가:

```typescript
export interface Persona {
  skills: SkillItem[];
  experiences: ExperienceItem[];
  education: EducationItem[];
  summary: string;
  certifications: CertificationItem[];
  languages: LanguageItem[];
  links: LinkItem[];
  projects: ProjectItem[];
  source?: string | null;
}
```

(기존 `EMPTY`에 `certifications: [], languages: [], links: [], projects: []` 추가. `PersonaUpsert` 타입이 별도면 동일 확장.)

- [ ] **Step 5: 훅 작성(usePersona 미러)**

`src/hooks/useProfile.ts`:

```typescript
// 기본정보 조회·저장 훅

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { BasicProfile, fetchProfile, upsertProfile } from "@/lib/api/profile";

export function useProfile(enabled = true) {
  return useQuery({ queryKey: ["profile"], queryFn: fetchProfile, enabled, staleTime: 5 * 60 * 1000, retry: 1 });
}

export function useUpsertProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Partial<BasicProfile>) => upsertProfile(payload),
    onSuccess: (saved: BasicProfile) => qc.setQueryData<BasicProfile>(["profile"], saved),
  });
}
```

`src/hooks/usePreferences.ts` — 위와 동일 구조로 `["preferences"]` 키, `fetchPreferences`/`upsertPreferences`.

- [ ] **Step 6: 타입 체크**

Run: `pnpm exec tsc --noEmit`
Expected: 0 에러. (이 태스크는 순수 TS — 컴파일만으로 검증.)

- [ ] **Step 7: 커밋**

```bash
git add src/lib/api/profile.ts src/lib/api/preferences.ts src/lib/api/persona.ts src/hooks/useProfile.ts src/hooks/usePreferences.ts src/data/personalizationOptions.ts
git commit -m "feat(profile): 개인화 선택 데이터 API 클라이언트·훅·옵션 상수"
```

---

### Task 2: 선택 섹션 컴포넌트(기본정보·성향·스펙·관심)

**Files:**
- Create: `src/components/features/profile/ChipSelect.tsx` (택1/다중 칩 공용)
- Create: `src/components/features/profile/BasicInfoSection.tsx`
- Create: `src/components/features/profile/PreferencesSection.tsx`
- Modify: `src/components/features/profile/PersonaForm.tsx` (스펙 4필드 동적 리스트 추가)
- Create: `src/components/features/profile/InterestSection.tsx`

**Interfaces (produces):**
- 각 섹션은 **자기완결형**(own draft state + 편집/저장 버튼 + 해당 훅으로 self-save), props `{ className?: string }`. 프로필·온보딩에서 동일 마운트.
- `ChipSelect`: props `{ options: Option[]; value: string | string[]; multi?: boolean; onChange: (v) => void }`.

- [ ] **Step 1: `ChipSelect.tsx` — 칩/세그먼트 공용 컴포넌트**

`src/components/features/profile/ChipSelect.tsx`:

```tsx
// 칩/세그먼트 선택 — 택1(multi=false) 또는 다중(multi=true)

"use client";

import { Option } from "@/data/personalizationOptions";

interface Props {
  options: Option[];
  value: string | string[] | null;
  multi?: boolean;
  onChange: (value: string | string[]) => void;
}

export default function ChipSelect({ options, value, multi = false, onChange }: Props) {
  const selected = (v: string) => (multi ? Array.isArray(value) && value.includes(v) : value === v);

  const toggle = (v: string) => {
    if (multi) {
      const cur = Array.isArray(value) ? value : [];
      onChange(cur.includes(v) ? cur.filter((x) => x !== v) : [...cur, v]);
    } else {
      onChange(value === v ? "" : v);
    }
  };

  return (
    <div className="flex flex-wrap gap-2">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          onClick={() => toggle(o.value)}
          className={`px-3 py-1.5 rounded-full text-sm border transition ${
            selected(o.value)
              ? "border-red-600 bg-red-600 text-white"
              : "border-gray-300 bg-white text-gray-700 hover:border-gray-400"
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: `BasicInfoSection.tsx`**

자기완결형 섹션. `useProfile()`로 초기값 로드, 로컬 draft 편집, `useUpsertProfile()`로 저장. 구조는 PersonaForm의 편집/읽기 토글 + 저장 버튼 패턴을 따른다. 필드:
- birthYear: number `<input type="number">`(빈값이면 null로 저장 — `value === "" ? null : Number(value)`).
- gender·currentStatus·educationLevel: `ChipSelect`(multi=false), 옵션은 personalizationOptions.
- region: text input(`inputCls` 스타일).
저장 시 `upsertProfile({ birthYear, gender: gender||null, region: region||null, currentStatus: currentStatus||null, educationLevel: educationLevel||null })`. 헤더에 "기본정보 · 선택 입력" + 안내 "채울수록 추천이 정확해져요.".

```tsx
// 기본정보(데모그래픽) 선택 입력 섹션 — 자기완결형

"use client";

import { useEffect, useState } from "react";

import ChipSelect from "./ChipSelect";
import {
  CURRENT_STATUS_OPTIONS,
  EDUCATION_OPTIONS,
  GENDER_OPTIONS,
} from "@/data/personalizationOptions";
import { useProfile, useUpsertProfile } from "@/hooks/useProfile";

const inputCls =
  "w-full px-3 py-2 border border-gray-300 rounded-md bg-white text-sm focus:outline-none focus:ring-2 focus:ring-red-500";

export default function BasicInfoSection({ className = "" }: { className?: string }) {
  const { data } = useProfile();
  const upsert = useUpsertProfile();
  const [birthYear, setBirthYear] = useState<string>("");
  const [gender, setGender] = useState<string>("");
  const [region, setRegion] = useState<string>("");
  const [currentStatus, setCurrentStatus] = useState<string>("");
  const [educationLevel, setEducationLevel] = useState<string>("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!data) return;
    setBirthYear(data.birthYear ? String(data.birthYear) : "");
    setGender(data.gender ?? "");
    setRegion(data.region ?? "");
    setCurrentStatus(data.currentStatus ?? "");
    setEducationLevel(data.educationLevel ?? "");
  }, [data]);

  const save = async () => {
    await upsert.mutateAsync({
      birthYear: birthYear === "" ? null : Number(birthYear),
      gender: gender || null,
      region: region || null,
      currentStatus: currentStatus || null,
      educationLevel: educationLevel || null,
    });
    setSaved(true);
    setTimeout(() => setSaved(false), 1500);
  };

  return (
    <section className={`rounded-lg border border-gray-200 p-4 ${className}`}>
      <h3 className="text-sm font-semibold text-gray-900 mb-1">기본정보 · 선택 입력</h3>
      <p className="text-xs text-gray-500 mb-3">채울수록 추천이 정확해져요.</p>
      <div className="space-y-3">
        <div>
          <label className="block text-xs text-gray-600 mb-1">출생연도</label>
          <input type="number" value={birthYear} onChange={(e) => setBirthYear(e.target.value)} placeholder="예) 1999" className={inputCls} />
        </div>
        <div>
          <label className="block text-xs text-gray-600 mb-1">성별</label>
          <ChipSelect options={GENDER_OPTIONS} value={gender} onChange={(v) => setGender(v as string)} />
        </div>
        <div>
          <label className="block text-xs text-gray-600 mb-1">현재 상태</label>
          <ChipSelect options={CURRENT_STATUS_OPTIONS} value={currentStatus} onChange={(v) => setCurrentStatus(v as string)} />
        </div>
        <div>
          <label className="block text-xs text-gray-600 mb-1">최종 학력</label>
          <ChipSelect options={EDUCATION_OPTIONS} value={educationLevel} onChange={(v) => setEducationLevel(v as string)} />
        </div>
        <div>
          <label className="block text-xs text-gray-600 mb-1">거주 지역</label>
          <input value={region} onChange={(e) => setRegion(e.target.value)} placeholder="예) 서울" className={inputCls} />
        </div>
        <button onClick={save} disabled={upsert.isPending} className="px-4 py-2 bg-red-600 text-white rounded-md text-sm hover:bg-red-700 disabled:opacity-50">
          {upsert.isPending ? "저장 중…" : saved ? "저장됨" : "저장"}
        </button>
      </div>
    </section>
  );
}
```

- [ ] **Step 3: `PreferencesSection.tsx`**

위 BasicInfoSection과 동일 패턴. `usePreferences()`/`useUpsertPreferences()`. 필드: workStyle·companySizePref·workTypePref = `ChipSelect` 택1, workValues = `ChipSelect` multi. 저장 `upsertPreferences({ workStyle: workStyle||null, companySizePref: companySizePref||null, workTypePref: workTypePref||null, workValues })`. 헤더 "성향·선호 · 선택 입력".

- [ ] **Step 4: `PersonaForm.tsx` 스펙 4필드 확장**

기존 PersonaForm의 동적 리스트 패턴(`addSkill`/`removeSkill` + map 렌더, `inputCls`)을 그대로 따라 4필드를 추가한다:
- certifications `[{name, issuer, year}]` — add/remove + 3 입력.
- languages `[{language, test, score}]` — add/remove + 3 입력.
- links `[{type, url}]` — type는 `<select>`(github/portfolio/blog) + url 입력.
- projects `[{title, description, role, period, tech_stack}]` — title·role·period·description 입력 + tech_stack은 콤마 분리 문자열↔배열.
`Draft` 타입·초기값·`save()`의 upsert payload에 4필드 포함(빈 배열 기본). 읽기모드는 기존처럼 배지. **기존 skills/experiences/education/summary·자동 /refine 연계는 보존.**

- [ ] **Step 5: `InterestSection.tsx`**

`useSyncProfile`(기존 `lib/api/user.ts`의 getSyncProfile/upsertSyncProfile, 훅 없으면 직접 호출 또는 간단 훅 추가) 사용. `INTEREST_SECTORS`+`JOB_FAMILIES`를 `ChipSelect` multi로 표시(라벨=저장값), 커스텀 입력(Enter 추가) 지원. targetJob 입력도 포함(기존 sync-profile이 targetJob+interestKeywords이므로 함께 저장). 저장 `upsertSyncProfile({ targetJob, interestKeywords })`. 헤더 "관심 분야 · 직무".

- [ ] **Step 6: 타입 체크**

Run: `pnpm exec tsc --noEmit`
Expected: 0 에러.

- [ ] **Step 7: 커밋**

```bash
git add src/components/features/profile/ChipSelect.tsx src/components/features/profile/BasicInfoSection.tsx src/components/features/profile/PreferencesSection.tsx src/components/features/profile/PersonaForm.tsx src/components/features/profile/InterestSection.tsx
git commit -m "feat(profile): 기본정보·성향·스펙·관심 선택 섹션 컴포넌트"
```

---

### Task 3: 프로필 페이지 통합 + 완성도 미터

**Files:**
- Create: `src/components/features/profile/CompletionMeter.tsx`
- Modify: `src/app/(main)/profile/page.tsx` (신규 섹션 마운트 + 미터)

**Interfaces (produces):** `CompletionMeter` — useProfile/usePreferences/usePersona/useSyncProfile 데이터로 채움 비율(0~100) 계산해 `components/ui/progress`로 표시.

- [ ] **Step 1: `CompletionMeter.tsx`**

채움 항목(가중 동일)을 세어 비율 산출. 항목 예: 기본정보 5(birthYear·gender·region·currentStatus·educationLevel), 성향 4(workStyle·companySize·workType·workValues 비어있지 않음), 스펙 4(skills·certifications·languages·projects 비어있지 않음), 관심 2(targetJob·interestKeywords 비어있지 않음) = 총 15. 채워진 수/15 × 100. `Progress` + "프로필 완성도 N%" 라벨 + "채울수록 Sync·Chance 추천이 정확해져요." 안내.

```tsx
// 프로필 완성도 미터 — 선택 데이터 채움 비율을 추천 정확도 넛지로 표시

"use client";

import { Progress } from "@/components/ui/progress";
import { useProfile } from "@/hooks/useProfile";
import { usePreferences } from "@/hooks/usePreferences";
import { usePersona } from "@/hooks/usePersona";
// useSyncProfile 또는 직접 fetch — 기존 user.ts 사용

export default function CompletionMeter() {
  const { data: profile } = useProfile();
  const { data: prefs } = usePreferences();
  const { data: persona } = usePersona();
  // const { data: sync } = useSyncProfile();

  const filled = [
    !!profile?.birthYear, !!profile?.gender, !!profile?.region, !!profile?.currentStatus, !!profile?.educationLevel,
    !!prefs?.workStyle, !!prefs?.companySizePref, !!prefs?.workTypePref, (prefs?.workValues?.length ?? 0) > 0,
    (persona?.skills?.length ?? 0) > 0, (persona?.certifications?.length ?? 0) > 0,
    (persona?.languages?.length ?? 0) > 0, (persona?.projects?.length ?? 0) > 0,
    // !!sync?.targetJob, (sync?.interestKeywords?.length ?? 0) > 0,
  ];
  const total = filled.length;
  const done = filled.filter(Boolean).length;
  const pct = Math.round((done / total) * 100);

  return (
    <div className="rounded-lg border border-gray-200 p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-semibold text-gray-900">프로필 완성도</span>
        <span className="text-sm text-red-600 font-semibold">{pct}%</span>
      </div>
      <Progress value={pct} />
      <p className="text-xs text-gray-500 mt-2">채울수록 Sync·Chance 추천이 정확해져요.</p>
    </div>
  );
}
```

(sync-profile 항목 포함 시 기존 `lib/api/user.ts` getSyncProfile을 쓰는 간단 훅 `useSyncProfile` 추가 — 또는 targetJob/interestKeywords는 InterestSection에서만 관리하고 미터에서 제외해도 됨. 구현 시 택일하고 total 일치시킬 것.)

- [ ] **Step 2: 프로필 페이지에 마운트**

`src/app/(main)/profile/page.tsx`에서 기존 PersonaForm 마운트(`<PersonaForm />`) 위/주변에 추가:

```tsx
<CompletionMeter />
<BasicInfoSection />
<PreferencesSection />
<PersonaForm />
<InterestSection />
```

(기존 상단 프로필 헤더·이름/이미지/기존 sync 편집 UI는 유지. InterestSection이 sync-profile을 다루므로, 기존 프로필 내 targetJob/interestKeywords 인라인 편집과 중복되면 InterestSection로 일원화하고 기존 인라인 편집 블록 제거 — 구현 시 중복 확인.)

- [ ] **Step 3: 타입 체크 + preview(베스트 에포트)**

Run: `pnpm exec tsc --noEmit` → 0 에러.
가능하면 preview로 `/profile` 렌더 확인(로그인 토큰 필요 — 안 되면 tsc로 대체, 보고서에 명시).

- [ ] **Step 4: 커밋**

```bash
git add src/components/features/profile/CompletionMeter.tsx "src/app/(main)/profile/page.tsx"
git commit -m "feat(profile): 선택 섹션 마운트 + 프로필 완성도 미터"
```

---

### Task 4: 온보딩 페이지 + 로그인 후 라우팅

**Files:**
- Create: `src/lib/onboarding.ts` (플래그·라우팅 유틸)
- Create: `src/app/onboarding/page.tsx`
- Modify: `src/app/auth/google/callback/page.tsx`
- Modify: `src/app/auth/kakao/callback/page.tsx`
- Modify: `src/app/auth/naver/callback/page.tsx`

**Interfaces (produces):** `onboardingTarget(): "/onboarding" | "/"`(플래그 없으면 온보딩), `markOnboardingDone(): void`.

- [ ] **Step 1: `lib/onboarding.ts`**

```typescript
// 온보딩 1회 유도 — 로그인 후 미완료 플래그 없으면 /onboarding 으로

const FLAG = "roadmap_onboarding_done";

export function onboardingTarget(): string {
  if (typeof window === "undefined") return "/";
  return localStorage.getItem(FLAG) ? "/" : "/onboarding";
}

export function markOnboardingDone(): void {
  if (typeof window !== "undefined") localStorage.setItem(FLAG, "1");
}
```

- [ ] **Step 2: `onboarding/page.tsx`**

인증 필요(토큰 없으면 `/login`). 인트로 + 4 섹션(Task 2 컴포넌트 재사용) + 하단 "완료" / "나중에 입력"(둘 다 `markOnboardingDone()` 후 `router.push("/")`).

```tsx
// 로그인 후 선택 온보딩 — 프로필 섹션 재사용, 건너뛰기 가능

"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import BasicInfoSection from "@/components/features/profile/BasicInfoSection";
import PreferencesSection from "@/components/features/profile/PreferencesSection";
import PersonaForm from "@/components/features/profile/PersonaForm";
import InterestSection from "@/components/features/profile/InterestSection";
import { markOnboardingDone } from "@/lib/onboarding";
import { useAuth } from "@/hooks/useStore";

export default function OnboardingPage() {
  const router = useRouter();
  const { isAuthenticated } = useAuth();

  useEffect(() => {
    if (!isAuthenticated) router.replace("/login");
  }, [isAuthenticated, router]);

  const finish = () => {
    markOnboardingDone();
    router.push("/");
  };

  return (
    <div className="min-h-screen bg-white px-4 py-10">
      <div className="max-w-2xl mx-auto">
        <h1 className="text-2xl font-bold text-gray-900 mb-1">프로필을 채워볼까요?</h1>
        <p className="text-sm text-gray-500 mb-6">선택 입력이에요. 채울수록 추천이 정확해지고, 언제든 건너뛸 수 있어요.</p>
        <div className="space-y-4">
          <BasicInfoSection />
          <PreferencesSection />
          <PersonaForm />
          <InterestSection />
        </div>
        <div className="flex gap-3 mt-8">
          <button onClick={finish} className="px-5 py-2 bg-red-600 text-white rounded-md hover:bg-red-700">완료</button>
          <button onClick={finish} className="px-5 py-2 border border-gray-300 text-gray-700 rounded-md hover:bg-gray-50">나중에 입력</button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: 3 OAuth 콜백 로그인 후 라우팅 교체**

각 콜백(`google`/`kakao`/`naver`)의 로그인 성공 분기에서 `router.push('/')`(약 google callback line 116)를 다음으로 교체. 상단에 `import { onboardingTarget } from "@/lib/onboarding";` 추가:

```tsx
setTimeout(() => {
    router.push(onboardingTarget());
}, 2000);
```

(`isSignupComplete`·`isNewUser` 분기는 변경하지 않는다 — 토큰 없는 경로. 기존 사용자 로그인 성공 경로만 온보딩 분기.)

- [ ] **Step 4: 타입 체크 + 플로우 확인(베스트 에포트)**

Run: `pnpm exec tsc --noEmit` → 0 에러.
가능하면 preview로 로그인→/onboarding 1회 유도, "나중에" 클릭 시 플래그 저장 후 재로그인 시 `/` 직행 확인(토큰 주입 필요 — 안 되면 tsc·코드리뷰로 대체, 보고서 명시).

- [ ] **Step 5: 커밋**

```bash
git add src/lib/onboarding.ts src/app/onboarding/page.tsx src/app/auth/google/callback/page.tsx src/app/auth/kakao/callback/page.tsx src/app/auth/naver/callback/page.tsx
git commit -m "feat(onboarding): 로그인 후 1회 선택 온보딩 + 콜백 라우팅"
```

---

## Phase 3 완료 기준

- `pnpm exec tsc --noEmit` 0 에러.
- 프로필 페이지에 기본정보·성향·스펙(확장)·관심 선택 섹션 + 완성도 미터가 마운트되고 각 섹션이 인증 PUT API로 저장된다.
- 로그인 후 온보딩 미완료 사용자는 `/onboarding`으로 1회 유도되고, 완료/건너뛰기 시 플래그 저장 후 재유도되지 않는다.
- 관심키워드 선택지가 12섹터+직무군(한국어 라벨=저장값)으로 재설계된다.
- 회원가입 필수 폼·OAuth 토큰 처리 로직 무변경(라우팅 분기만 추가).

## Phase 3 범위 밖(후속)

- signup 페이지의 기존 8개 뉴스 카테고리 프리셋 교체(가입 전 폼 — 이번엔 프로필/온보딩만 신규 풀 사용; 통일은 후속).
- 대화형 추출(ai_coach)·필드별 provenance.
- preview 픽셀 스크린샷이 토큰 주입 제약으로 막히면 tsc + 코드리뷰로 대체(시각 회귀는 수동).
- 비차단 정리(누적): scheduler user_embed 순서, 마이그 COMMENT/em-dash, upsert echo, 인증 가드 수렴.
