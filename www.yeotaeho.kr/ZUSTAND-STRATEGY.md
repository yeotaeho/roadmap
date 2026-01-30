# Zustand 단일 Store 관리 전략

## 📋 목차
1. [개요](#개요)
2. [Zustand 선택 이유](#zustand-선택-이유)
3. [아키텍처 설계](#아키텍처-설계)
4. [폴더 구조](#폴더-구조)
5. [구현 전략](#구현-전략)
6. [Best Practices](#best-practices)
7. [구현 단계](#구현-단계)

---

## 개요

### 목표
- **단일 Store**: 애플리케이션 전역 상태를 하나의 중앙 집중식 Store로 관리
- **타입 안전성**: TypeScript를 활용한 완벽한 타입 추론
- **확장성**: Slice 패턴을 통한 모듈화된 상태 관리
- **개발자 경험**: Redux DevTools 통합 및 간결한 API

### Zustand란?
- 경량 상태 관리 라이브러리 (3KB gzipped)
- React Hooks 기반의 직관적인 API
- Boilerplate 최소화
- Next.js SSR/SSG 완벽 지원

---

## Zustand 선택 이유

### 1. **간결성**
```typescript
// Redux
const ADD_TODO = 'ADD_TODO';
function addTodo(text) { return { type: ADD_TODO, text }; }
function todoReducer(state = [], action) { /* ... */ }

// Zustand
const useStore = create((set) => ({
  todos: [],
  addTodo: (text) => set((state) => ({ todos: [...state.todos, text] }))
}));
```

### 2. **성능**
- 불필요한 리렌더링 방지 (선택적 구독)
- Context API의 성능 문제 해결
- 메모이제이션 자동 최적화

### 3. **개발자 경험**
- Redux DevTools 지원
- 미들웨어 생태계 (persist, immer, devtools)
- TypeScript 완벽 지원

### 4. **Next.js 호환성**
- SSR/SSG 환경에서 안전한 상태 관리
- Hydration 이슈 최소화
- 클라이언트/서버 상태 분리 용이

---

## 아키텍처 설계

### 단일 Store 구조
```
┌─────────────────────────────────────┐
│         Global Store (Root)          │
├─────────────────────────────────────┤
│  ┌─────────┐  ┌─────────┐  ┌──────┐│
│  │  Auth   │  │  User   │  │  UI  ││
│  │  Slice  │  │  Slice  │  │ Slice││
│  └─────────┘  └─────────┘  └──────┘│
│                                      │
│  ┌──────────────────────────────┐  │
│  │      Middleware Layer        │  │
│  │  - DevTools                  │  │
│  │  - Persist (optional)        │  │
│  │  - Logger (dev only)         │  │
│  └──────────────────────────────┘  │
└─────────────────────────────────────┘
```

### Slice 패턴
각 Slice는 독립적인 도메인 로직을 담당하며, 하나의 Store로 통합됩니다.

**장점:**
- 코드 분리 및 모듈화
- 각 도메인별 독립적 개발
- 타입 안전성 유지
- 테스트 용이성

---

## 폴더 구조

```
src/
├── app/                    # Next.js App Router
│   ├── layout.tsx
│   └── page.tsx
│
├── store/                  # Zustand Store (단일 Store)
│   ├── index.ts           # Store 생성 및 통합
│   ├── types.ts           # 전역 타입 정의
│   │
│   └── slices/            # Slice 패턴
│       ├── authSlice.ts   # 인증 관련 상태
│       ├── userSlice.ts   # 유저 프로필 상태
│       └── uiSlice.ts     # UI 관련 상태 (모달, 토스트 등)
│
├── hooks/                 # Custom Hooks
│   └── useStore.ts        # Store 접근용 Hooks
│
├── lib/                   # 유틸리티
│   └── api.ts            # API 호출 함수
│
└── components/            # React 컴포넌트
    ├── Header.tsx
    └── LoginForm.tsx
```

---

## 구현 전략

### 1. Store 생성 (`store/index.ts`)

```typescript
import { create } from 'zustand';
import { devtools, persist } from 'zustand/middleware';
import { createAuthSlice } from './slices/authSlice';
import { createUserSlice } from './slices/userSlice';
import { createUISlice } from './slices/uiSlice';
import { StoreState } from './types';

/**
 * 전역 단일 Store
 * - 모든 Slice를 통합하여 하나의 Store로 관리
 * - DevTools: Redux DevTools 지원
 * - Persist: 선택적 상태 영속화 (localStorage)
 */
export const useStore = create<StoreState>()(
  devtools(
    persist(
      (...a) => ({
        ...createAuthSlice(...a),
        ...createUserSlice(...a),
        ...createUISlice(...a),
      }),
      {
        name: 'app-storage', // localStorage key
        partialize: (state) => ({
          // 영속화할 상태만 선택
          token: state.token,
          theme: state.theme,
        }),
      }
    ),
    {
      name: 'AppStore', // DevTools에서 보이는 이름
      enabled: process.env.NODE_ENV === 'development',
    }
  )
);

// Named exports
export * from './types';
```

### 2. 타입 정의 (`store/types.ts`)

```typescript
import { StateCreator } from 'zustand';

// Auth Slice
export interface AuthSlice {
  token: string | null;
  isAuthenticated: boolean;
  login: (token: string) => void;
  logout: () => void;
  setToken: (token: string | null) => void;
}

// User Slice
export interface UserSlice {
  profile: UserProfile | null;
  isLoading: boolean;
  error: string | null;
  setProfile: (profile: UserProfile) => void;
  updateProfile: (data: Partial<UserProfile>) => void;
  clearProfile: () => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
}

// UI Slice
export interface UISlice {
  theme: 'light' | 'dark';
  modals: Record<string, ModalState>;
  toasts: Toast[];
  setTheme: (theme: 'light' | 'dark') => void;
  openModal: (id: string, data?: unknown) => void;
  closeModal: (id: string) => void;
  addToast: (toast: Omit<Toast, 'id'>) => void;
  removeToast: (id: string) => void;
  setGlobalLoading: (loading: boolean) => void;
}

// Global Store State (모든 Slice 통합)
export type StoreState = AuthSlice & UserSlice & UISlice;

// Slice Creator 타입 (TypeScript 타입 추론용)
export type SliceCreator<T> = StateCreator<
  StoreState,
  [['zustand/devtools', never], ['zustand/persist', unknown]],
  [],
  T
>;

// 도메인 모델
export interface UserProfile {
  id: string;
  name: string;
  email: string;
  avatar?: string;
}

export interface ModalState {
  isOpen: boolean;
  data?: unknown;
}

export interface Toast {
  id: string;
  type: 'success' | 'error' | 'warning' | 'info';
  message: string;
  duration?: number;
}
```

### 3. Slice 구현 예시 (`store/slices/authSlice.ts`)

```typescript
import { SliceCreator, AuthSlice } from '../types';

export const createAuthSlice: SliceCreator<AuthSlice> = (set, get) => ({
  token: null,
  isAuthenticated: false,

  login: (token: string) => {
    set(
      {
        token,
        isAuthenticated: true,
      },
      false, // replace 옵션
      'auth/login' // DevTools 액션 이름
    );
  },

  logout: () => {
    set(
      {
        token: null,
        isAuthenticated: false,
      },
      false,
      'auth/logout'
    );
    // 다른 Slice 상태도 리셋 가능
    get().clearProfile();
  },

  setToken: (token: string | null) => {
    set(
      {
        token,
        isAuthenticated: !!token,
      },
      false,
      'auth/setToken'
    );
  },
});
```

### 4. Custom Hooks (`hooks/useStore.ts`)

```typescript
import { useStore as useZustandStore } from '@/store';
import { StoreState } from '@/store/types';

/**
 * 선택적 구독을 위한 Custom Hooks
 * 성능 최적화: 필요한 상태만 구독
 */

// Auth Hook
export const useAuth = () =>
  useZustandStore((state: StoreState) => ({
    token: state.token,
    isAuthenticated: state.isAuthenticated,
    login: state.login,
    logout: state.logout,
    setToken: state.setToken,
  }));

// User Profile Hook
export const useUserProfile = () =>
  useZustandStore((state: StoreState) => state.profile);

export const useUserActions = () =>
  useZustandStore((state: StoreState) => ({
    setProfile: state.setProfile,
    updateProfile: state.updateProfile,
    clearProfile: state.clearProfile,
  }));

// UI Hook
export const useTheme = () =>
  useZustandStore((state: StoreState) => ({
    theme: state.theme,
    setTheme: state.setTheme,
  }));

export const useModal = (modalId: string) =>
  useZustandStore((state: StoreState) => ({
    isOpen: state.modals[modalId]?.isOpen ?? false,
    data: state.modals[modalId]?.data,
    openModal: (data?: unknown) => state.openModal(modalId, data),
    closeModal: () => state.closeModal(modalId),
  }));

export const useToasts = () =>
  useZustandStore((state: StoreState) => ({
    toasts: state.toasts,
    addToast: state.addToast,
    removeToast: state.removeToast,
  }));
```

### 5. 컴포넌트에서 사용

```typescript
'use client';

import { useAuth, useUserProfile } from '@/hooks/useStore';

export default function Header() {
  const { isAuthenticated, logout } = useAuth();
  const profile = useUserProfile();

  return (
    <header>
      {isAuthenticated ? (
        <>
          <span>Welcome, {profile?.name}</span>
          <button onClick={logout}>Logout</button>
        </>
      ) : (
        <a href="/login">Login</a>
      )}
    </header>
  );
}
```

---

## Best Practices

### 1. **선택적 구독 (Selective Subscription)**
```typescript
// ❌ 나쁜 예: 전체 Store 구독
const store = useStore();

// ✅ 좋은 예: 필요한 상태만 구독
const isAuthenticated = useStore((state) => state.isAuthenticated);
```

### 2. **액션 분리**
```typescript
// ✅ 액션과 상태 분리
const token = useStore((state) => state.token);
const setToken = useStore((state) => state.setToken);
```

### 3. **DevTools 활용**
```typescript
set(
  { count: state.count + 1 },
  false,
  'counter/increment' // DevTools에서 추적 가능
);
```

### 4. **비동기 처리**
```typescript
fetchUser: async (userId: string) => {
  set({ isLoading: true, error: null });
  try {
    const user = await api.getUser(userId);
    set({ profile: user, isLoading: false });
  } catch (error) {
    set({ error: error.message, isLoading: false });
  }
}
```

### 5. **Next.js SSR 고려**
```typescript
// Client Component에서만 사용
'use client';

// 또는 dynamic import
import dynamic from 'next/dynamic';
const Component = dynamic(() => import('./Component'), { ssr: false });
```

---

## 구현 단계

### Phase 1: 설치 및 기본 설정
1. Zustand 설치
   ```bash
   npm install zustand
   ```

2. 폴더 구조 생성
   ```bash
   mkdir -p src/store/slices src/hooks
   ```

3. 타입 정의 파일 생성 (`store/types.ts`)

### Phase 2: Slice 구현
4. Auth Slice 구현
5. User Slice 구현
6. UI Slice 구현

### Phase 3: Store 통합
7. Store 생성 및 Slice 통합 (`store/index.ts`)
8. Middleware 설정 (devtools, persist)

### Phase 4: Hooks 작성
9. Custom Hooks 작성 (`hooks/useStore.ts`)
10. 성능 최적화 (선택적 구독)

### Phase 5: 통합 및 테스트
11. 컴포넌트에서 Store 사용
12. DevTools로 디버깅
13. SSR/CSR 동작 확인

---

## 주의사항

### 1. **Persist 주의사항**
- Next.js SSR 환경에서 `persist` 미들웨어 사용 시 hydration 이슈 주의
- 민감한 정보 (토큰 등)는 localStorage 대신 HTTP-only Cookie 사용 권장

### 2. **성능**
- 큰 객체를 상태로 관리할 때는 immer 미들웨어 고려
- 불필요한 리렌더링 방지를 위해 선택적 구독 필수

### 3. **타입 안전성**
- 모든 Slice에 명확한 타입 정의
- `StoreState` 타입을 통한 전역 타입 추론

---

## 참고 자료

- [Zustand 공식 문서](https://zustand-demo.pmnd.rs/)
- [Zustand GitHub](https://github.com/pmndrs/zustand)
- [Next.js State Management](https://nextjs.org/docs/app/building-your-application/data-fetching/patterns)
- [TypeScript Deep Dive](https://basarat.gitbook.io/typescript/)

---

## 결론

Zustand를 사용한 단일 Store 패턴은:
- ✅ 간결하고 유지보수 용이
- ✅ TypeScript 완벽 지원
- ✅ 성능 최적화 (선택적 구독)
- ✅ Next.js SSR/SSG 호환
- ✅ 확장 가능한 아키텍처 (Slice 패턴)

이 전략을 따라 구현하면 확장 가능하고 유지보수 가능한 전역 상태 관리 시스템을 구축할 수 있습니다.
