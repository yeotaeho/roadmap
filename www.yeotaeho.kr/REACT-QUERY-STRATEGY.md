# React Query (TanStack Query) 전략

## 📋 목차
1. [개요](#개요)
2. [React Query 선택 이유](#react-query-선택-이유)
3. [Zustand와의 역할 분담](#zustand와의-역할-분담)
4. [아키텍처 설계](#아키텍처-설계)
5. [폴더 구조](#폴더-구조)
6. [구현 전략](#구현-전략)
7. [Server Component & Hydration 전략](#server-component--hydration-전략)
8. [Best Practices](#best-practices)
9. [구현 단계](#구현-단계)
10. [프리패치 최적화 전략](#프리패치-최적화-전략)
11. [데이터 직렬화 문제 해결](#데이터-직렬화-문제-해결)

---

## 개요

### 목표
- **서버 상태 관리**: API 데이터 패칭, 캐싱, 동기화
- **자동 리패칭**: Background refetching, polling
- **최적화**: 중복 요청 제거, 캐싱 전략
- **개발자 경험**: DevTools, 에러 핸들링, 로딩 상태

### React Query란?
- 서버 상태 관리에 특화된 라이브러리
- 자동 캐싱, 리패칭, 백그라운드 업데이트
- Next.js SSR/SSG 완벽 지원
- Optimistic Updates, Infinite Scroll 지원

---

## React Query 선택 이유

### 1. **서버 상태 관리의 복잡성 해결**
```typescript
// ❌ 기존 방식 (Zustand만 사용)
const fetchUser = async (userId: string) => {
  set({ isLoading: true, error: null });
  try {
    const user = await api.getUser(userId);
    set({ user, isLoading: false });
  } catch (error) {
    set({ error: error.message, isLoading: false });
  }
};

// ✅ React Query 사용
const { data: user, isLoading, error } = useQuery({
  queryKey: ['user', userId],
  queryFn: () => api.getUser(userId),
});
```

### 2. **자동 캐싱 & 동기화**
- 동일한 데이터에 대한 중복 요청 자동 제거
- 백그라운드에서 자동 리패칭
- Stale-While-Revalidate 패턴

### 3. **성능 최적화**
- 자동 가비지 컬렉션
- Pagination, Infinite Scroll 내장 지원
- Prefetching, Optimistic Updates

### 4. **개발자 경험**
- React Query DevTools
- 강력한 타입 추론
- 에러 핸들링 및 재시도 로직 내장

---

## Zustand와의 역할 분담

### 상태 관리 책임 분리

```
┌─────────────────────────────────────────────────────┐
│                 애플리케이션 상태                      │
├─────────────────────────────────────────────────────┤
│                                                       │
│  ┌──────────────────┐      ┌────────────────────┐  │
│  │     Zustand      │      │   React Query      │  │
│  │  (클라이언트 상태) │      │   (서버 상태)       │  │
│  ├──────────────────┤      ├────────────────────┤  │
│  │ - UI 상태        │      │ - API 데이터        │  │
│  │ - 인증 토큰      │      │ - 캐싱             │  │
│  │ - 테마           │      │ - 자동 리패칭       │  │
│  │ - 모달/토스트    │      │ - 서버 동기화       │  │
│  │ - 전역 플래그    │      │ - Pagination       │  │
│  └──────────────────┘      └────────────────────┘  │
│                                                       │
└─────────────────────────────────────────────────────┘
```

### Zustand (클라이언트 상태)
- ✅ UI 상태 (모달, 사이드바, 테마)
- ✅ 인증 토큰 (localStorage 저장)
- ✅ 사용자 선택/입력 상태
- ✅ 전역 플래그 (isOnline, isDarkMode)

### React Query (서버 상태)
- ✅ API 데이터 (유저 정보, 게시물 등)
- ✅ 데이터 캐싱 및 동기화
- ✅ 서버 뮤테이션 (POST, PUT, DELETE)
- ✅ 백그라운드 리패칭

---

## 아키텍처 설계

### 전체 구조

```
┌────────────────────────────────────────────────────┐
│              Next.js App (Client)                   │
├────────────────────────────────────────────────────┤
│                                                      │
│  ┌──────────────────────────────────────────────┐ │
│  │         QueryClientProvider                   │ │
│  │  ┌────────────────────────────────────────┐  │ │
│  │  │         React Components               │  │ │
│  │  │                                         │  │ │
│  │  │  ┌──────────┐      ┌──────────────┐   │  │ │
│  │  │  │ Zustand  │      │ React Query  │   │  │ │
│  │  │  │  Hooks   │      │   Hooks      │   │  │ │
│  │  │  └──────────┘      └──────────────┘   │  │ │
│  │  │       ↓                    ↓            │  │ │
│  │  │  ┌──────────┐      ┌──────────────┐   │  │ │
│  │  │  │  Store   │      │ Query Cache  │   │  │ │
│  │  │  └──────────┘      └──────────────┘   │  │ │
│  │  └────────────────────────────────────────┘  │ │
│  └──────────────────────────────────────────────┘ │
│                                                      │
│  ┌──────────────────────────────────────────────┐ │
│  │              API Layer                        │ │
│  │  - Axios / Fetch                              │ │
│  │  - Interceptors (토큰 주입)                   │ │
│  │  - Error Handling                             │ │
│  └──────────────────────────────────────────────┘ │
│                          ↓                          │
└──────────────────────────────────────────────────┘
                           ↓
                    Backend API
```

---

## 폴더 구조

```
src/
├── app/
│   ├── layout.tsx              # QueryClientProvider 설정
│   └── page.tsx
│
├── lib/
│   ├── react-query/
│   │   ├── query-client.ts     # QueryClient 설정
│   │   ├── query-keys.ts       # Query Key Factory
│   │   └── query-provider.tsx  # Provider 컴포넌트
│   │
│   └── api/
│       ├── client.ts           # Axios/Fetch 인스턴스
│       ├── endpoints.ts        # API 엔드포인트 상수
│       └── interceptors.ts     # 요청/응답 인터셉터
│
├── hooks/
│   ├── queries/                # Query Hooks
│   │   ├── useUserQuery.ts     # 유저 데이터 조회
│   │   ├── usePostsQuery.ts    # 게시물 목록 조회
│   │   └── useProfileQuery.ts  # 프로필 조회
│   │
│   ├── mutations/              # Mutation Hooks
│   │   ├── useLoginMutation.ts
│   │   ├── useUpdateProfileMutation.ts
│   │   └── useCreatePostMutation.ts
│   │
│   └── useStore.ts             # Zustand Hooks
│
├── store/                      # Zustand Store
│   ├── index.ts
│   ├── types.ts
│   └── slices/
│
└── types/
    └── api.ts                  # API 응답 타입
```

---

## 구현 전략

### 1. QueryClient 설정 (`lib/react-query/query-client.ts`)

```typescript
import { QueryClient } from '@tanstack/react-query';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // 데이터가 5분간 fresh 상태 유지
      staleTime: 1000 * 60 * 5,
      
      // 캐시 유지 시간 (10분)
      gcTime: 1000 * 60 * 10,
      
      // 에러 발생 시 재시도 횟수
      retry: 1,
      
      // 윈도우 포커스 시 자동 리패칭 (개발 중에는 false 권장)
      refetchOnWindowFocus: process.env.NODE_ENV === 'production',
      
      // 마운트 시 자동 리패칭
      refetchOnMount: true,
      
      // 네트워크 재연결 시 리패칭
      refetchOnReconnect: true,
    },
    mutations: {
      // 뮤테이션 에러 시 재시도
      retry: 0,
    },
  },
});
```

### 2. Provider 설정 (`lib/react-query/query-provider.tsx`)

```typescript
'use client';

import { QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { queryClient } from './query-client';

export function QueryProvider({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      {children}
      {/* 개발 환경에서만 DevTools 표시 */}
      {process.env.NODE_ENV === 'development' && (
        <ReactQueryDevtools initialIsOpen={false} position="bottom-right" />
      )}
    </QueryClientProvider>
  );
}
```

### 3. Root Layout 설정 (`app/layout.tsx`)

```typescript
import { QueryProvider } from '@/lib/react-query/query-provider';

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>
        <QueryProvider>
          {children}
        </QueryProvider>
      </body>
    </html>
  );
}
```

### 4. Query Keys Factory (`lib/react-query/query-keys.ts`)

```typescript
/**
 * Query Key Factory
 * - 일관된 Query Key 생성
 * - 타입 안전성 보장
 * - 캐시 무효화 용이
 */

export const queryKeys = {
  // Auth
  auth: {
    all: ['auth'] as const,
    me: () => [...queryKeys.auth.all, 'me'] as const,
  },

  // Users
  users: {
    all: ['users'] as const,
    lists: () => [...queryKeys.users.all, 'list'] as const,
    list: (filters: string) => [...queryKeys.users.lists(), { filters }] as const,
    details: () => [...queryKeys.users.all, 'detail'] as const,
    detail: (id: string) => [...queryKeys.users.details(), id] as const,
  },

  // Posts
  posts: {
    all: ['posts'] as const,
    lists: () => [...queryKeys.posts.all, 'list'] as const,
    list: (filters: string) => [...queryKeys.posts.lists(), { filters }] as const,
    details: () => [...queryKeys.posts.all, 'detail'] as const,
    detail: (id: string) => [...queryKeys.posts.details(), id] as const,
  },
};

// 사용 예시:
// queryKeys.users.detail('123') → ['users', 'detail', '123']
// queryKeys.posts.list('filter=active') → ['posts', 'list', { filters: 'filter=active' }]
```

### 5. API Client (`lib/api/client.ts`)

```typescript
import axios from 'axios';
import { useStore } from '@/store';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true, // 쿠키 포함
});

// 요청 인터셉터: 토큰 자동 주입
apiClient.interceptors.request.use(
  (config) => {
    const token = useStore.getState().token;
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// 응답 인터셉터: 에러 처리
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // 인증 실패 시 로그아웃
      useStore.getState().logout();
    }
    return Promise.reject(error);
  }
);
```

### 6. Query Hook 예시 (`hooks/queries/useUserQuery.ts`)

```typescript
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import { queryKeys } from '@/lib/react-query/query-keys';

interface User {
  id: string;
  name: string;
  email: string;
  avatar?: string;
}

// 유저 조회 API
const fetchUser = async (userId: string): Promise<User> => {
  const { data } = await apiClient.get(`/api/users/${userId}`);
  return data;
};

// useUserQuery Hook
export const useUserQuery = (userId: string) => {
  return useQuery({
    queryKey: queryKeys.users.detail(userId),
    queryFn: () => fetchUser(userId),
    enabled: !!userId, // userId가 있을 때만 실행
    staleTime: 1000 * 60 * 5, // 5분
  });
};

// 사용 예시:
// const { data: user, isLoading, error, refetch } = useUserQuery('123');
```

### 7. Mutation Hook 예시 (`hooks/mutations/useLoginMutation.ts`)

```typescript
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';
import { apiClient } from '@/lib/api/client';
import { queryKeys } from '@/lib/react-query/query-keys';
import { useAuth } from '@/hooks/useStore';

interface LoginRequest {
  email: string;
  password: string;
}

interface LoginResponse {
  token: string;
  user: {
    id: string;
    name: string;
    email: string;
  };
}

// 로그인 API
const loginApi = async (data: LoginRequest): Promise<LoginResponse> => {
  const response = await apiClient.post('/api/auth/login', data);
  return response.data;
};

// useLoginMutation Hook
export const useLoginMutation = () => {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { login } = useAuth();

  return useMutation({
    mutationFn: loginApi,
    onSuccess: (data) => {
      // 1. Zustand에 토큰 저장
      login(data.token);

      // 2. 유저 캐시 업데이트
      queryClient.setQueryData(queryKeys.auth.me(), data.user);

      // 3. 대시보드로 이동
      router.push('/dashboard');
    },
    onError: (error: any) => {
      console.error('로그인 실패:', error);
      alert('로그인에 실패했습니다.');
    },
  });
};

// 사용 예시:
// const { mutate: login, isPending } = useLoginMutation();
// login({ email, password });
```

### 8. 무한 스크롤 예시 (`hooks/queries/usePostsInfiniteQuery.ts`)

```typescript
import { useInfiniteQuery } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import { queryKeys } from '@/lib/react-query/query-keys';

interface Post {
  id: string;
  title: string;
  content: string;
}

interface PostsResponse {
  posts: Post[];
  nextCursor: number | null;
}

// 게시물 목록 조회
const fetchPosts = async ({ pageParam = 0 }): Promise<PostsResponse> => {
  const { data } = await apiClient.get('/api/posts', {
    params: { cursor: pageParam, limit: 20 },
  });
  return data;
};

export const usePostsInfiniteQuery = () => {
  return useInfiniteQuery({
    queryKey: queryKeys.posts.lists(),
    queryFn: fetchPosts,
    initialPageParam: 0,
    getNextPageParam: (lastPage) => lastPage.nextCursor,
  });
};

// 사용 예시:
// const { data, fetchNextPage, hasNextPage, isFetchingNextPage } = usePostsInfiniteQuery();
```

### 9. Optimistic Update 예시

```typescript
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '@/lib/api/client';
import { queryKeys } from '@/lib/react-query/query-keys';

interface UpdateProfileRequest {
  name: string;
  bio: string;
}

export const useUpdateProfileMutation = (userId: string) => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: UpdateProfileRequest) =>
      apiClient.patch(`/api/users/${userId}`, data),

    // Optimistic Update
    onMutate: async (newData) => {
      // 이전 쿼리 취소
      await queryClient.cancelQueries({ queryKey: queryKeys.users.detail(userId) });

      // 이전 데이터 백업
      const previousUser = queryClient.getQueryData(queryKeys.users.detail(userId));

      // 낙관적 업데이트 (UI 즉시 반영)
      queryClient.setQueryData(queryKeys.users.detail(userId), (old: any) => ({
        ...old,
        ...newData,
      }));

      // 롤백용 컨텍스트 반환
      return { previousUser };
    },

    // 에러 발생 시 롤백
    onError: (err, newData, context) => {
      if (context?.previousUser) {
        queryClient.setQueryData(
          queryKeys.users.detail(userId),
          context.previousUser
        );
      }
    },

    // 성공 시 최신 데이터로 리패칭
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.users.detail(userId) });
    },
  });
};
```

---

## Best Practices

### 1. **Query Key 일관성**
```typescript
// ❌ 나쁜 예: 하드코딩
useQuery({ queryKey: ['user', userId] });

// ✅ 좋은 예: Factory 사용
useQuery({ queryKey: queryKeys.users.detail(userId) });
```

### 2. **에러 핸들링**
```typescript
const { data, error, isError } = useUserQuery('123');

if (isError) {
  return <ErrorMessage error={error} />;
}
```

### 3. **캐시 무효화**
```typescript
// 특정 쿼리 무효화
queryClient.invalidateQueries({ queryKey: queryKeys.users.detail('123') });

// 모든 유저 쿼리 무효화
queryClient.invalidateQueries({ queryKey: queryKeys.users.all });
```

### 4. **Prefetching**
```typescript
// 마우스 호버 시 데이터 미리 가져오기
const handleMouseEnter = () => {
  queryClient.prefetchQuery({
    queryKey: queryKeys.users.detail('123'),
    queryFn: () => fetchUser('123'),
  });
};
```

### 5. **Zustand와 연동**
```typescript
// React Query로 데이터 패칭
const { data: user } = useUserQuery('123');

// Zustand로 클라이언트 상태 관리
const { theme, setTheme } = useTheme();
```

---

## Server Component & Hydration 전략

### 개요

**문제점**: `useQuery`는 Client Component에서만 동작하므로 모든 컴포넌트가 `'use client'`로 동작하면 Server Component의 장점을 잃게 됩니다.

**해결책**: Server Component에서 데이터를 프리패치하고, `dehydrate`/`HydrationBoundary`를 사용하여 Client Component에 전달합니다.

### 장점

✅ **SEO 최적화**: 서버에서 렌더링된 완전한 HTML  
✅ **초기 로딩 성능**: 클라이언트 API 요청 불필요  
✅ **사용자 경험**: 로딩 스피너 없이 즉시 콘텐츠 표시  
✅ **Next.js 장점 극대화**: SSR/SSG 완벽 활용  

---

### 1. 기본 Hydration 패턴

#### Server Component에서 프리패치

```typescript
// app/users/[id]/page.tsx (Server Component)
import { dehydrate, HydrationBoundary, QueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/lib/react-query/query-keys';
import { fetchUser } from '@/lib/api/users';
import UserProfile from './UserProfile';

export default async function UserPage({ params }: { params: { id: string } }) {
  const queryClient = new QueryClient();

  // 서버에서 데이터 프리패치
  await queryClient.prefetchQuery({
    queryKey: queryKeys.users.detail(params.id),
    queryFn: () => fetchUser(params.id),
  });

  return (
    <HydrationBoundary state={dehydrate(queryClient)}>
      <UserProfile userId={params.id} />
    </HydrationBoundary>
  );
}
```

#### Client Component에서 사용

```typescript
// app/users/[id]/UserProfile.tsx (Client Component)
'use client';

import { useQuery } from '@tanstack/react-query';
import { queryKeys } from '@/lib/react-query/query-keys';
import { fetchUser } from '@/lib/api/users';

export default function UserProfile({ userId }: { userId: string }) {
  // 서버에서 프리패치된 데이터를 자동으로 사용
  const { data: user, isLoading } = useQuery({
    queryKey: queryKeys.users.detail(userId),
    queryFn: () => fetchUser(userId),
  });

  // 초기 렌더링 시 이미 데이터가 있으므로 isLoading은 false
  if (isLoading) return <div>Loading...</div>;

  return (
    <div>
      <h1>{user.name}</h1>
      <p>{user.email}</p>
    </div>
  );
}
```

---

### 2. 여러 쿼리 프리패치

```typescript
// app/dashboard/page.tsx
import { dehydrate, HydrationBoundary, QueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/lib/react-query/query-keys';
import { fetchUser, fetchPosts, fetchStats } from '@/lib/api';
import Dashboard from './Dashboard';

export default async function DashboardPage() {
  const queryClient = new QueryClient();

  // 여러 쿼리를 병렬로 프리패치
  await Promise.all([
    queryClient.prefetchQuery({
      queryKey: queryKeys.auth.me(),
      queryFn: fetchUser,
    }),
    queryClient.prefetchQuery({
      queryKey: queryKeys.posts.lists(),
      queryFn: fetchPosts,
    }),
    queryClient.prefetchQuery({
      queryKey: ['stats'],
      queryFn: fetchStats,
    }),
  ]);

  return (
    <HydrationBoundary state={dehydrate(queryClient)}>
      <Dashboard />
    </HydrationBoundary>
  );
}
```

---

### 3. Streaming SSR과 함께 사용

```typescript
// app/posts/page.tsx
import { Suspense } from 'react';
import { dehydrate, HydrationBoundary, QueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/lib/react-query/query-keys';
import { fetchPosts } from '@/lib/api/posts';
import PostsList from './PostsList';
import PostsSkeleton from './PostsSkeleton';

export default async function PostsPage() {
  const queryClient = new QueryClient();

  await queryClient.prefetchQuery({
    queryKey: queryKeys.posts.lists(),
    queryFn: fetchPosts,
  });

  return (
    <div>
      <h1>게시물 목록</h1>
      
      {/* Suspense로 Streaming 처리 */}
      <Suspense fallback={<PostsSkeleton />}>
        <HydrationBoundary state={dehydrate(queryClient)}>
          <PostsList />
        </HydrationBoundary>
      </Suspense>
    </div>
  );
}
```

---

### 4. 조건부 프리패치

```typescript
// app/search/page.tsx
import { dehydrate, HydrationBoundary, QueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/lib/react-query/query-keys';
import { searchPosts } from '@/lib/api/search';
import SearchResults from './SearchResults';

interface SearchPageProps {
  searchParams: { q?: string };
}

export default async function SearchPage({ searchParams }: SearchPageProps) {
  const queryClient = new QueryClient();
  const query = searchParams.q;

  // 검색어가 있을 때만 프리패치
  if (query) {
    await queryClient.prefetchQuery({
      queryKey: queryKeys.posts.list(`search=${query}`),
      queryFn: () => searchPosts(query),
    });
  }

  return (
    <HydrationBoundary state={dehydrate(queryClient)}>
      <SearchResults initialQuery={query} />
    </HydrationBoundary>
  );
}
```

---

### 5. 유틸리티 함수로 추상화

```typescript
// lib/react-query/prefetch-helpers.ts
import { QueryClient, dehydrate } from '@tanstack/react-query';

export async function prefetchQueries(
  queries: Array<{
    queryKey: any[];
    queryFn: () => Promise<any>;
  }>
) {
  const queryClient = new QueryClient();

  await Promise.all(
    queries.map((query) =>
      queryClient.prefetchQuery({
        queryKey: query.queryKey,
        queryFn: query.queryFn,
      })
    )
  );

  return dehydrate(queryClient);
}

// 사용 예시
// app/users/[id]/page.tsx
import { HydrationBoundary } from '@tanstack/react-query';
import { prefetchQueries } from '@/lib/react-query/prefetch-helpers';
import { queryKeys } from '@/lib/react-query/query-keys';
import { fetchUser, fetchUserPosts } from '@/lib/api/users';

export default async function UserPage({ params }: { params: { id: string } }) {
  const dehydratedState = await prefetchQueries([
    {
      queryKey: queryKeys.users.detail(params.id),
      queryFn: () => fetchUser(params.id),
    },
    {
      queryKey: queryKeys.posts.list(`userId=${params.id}`),
      queryFn: () => fetchUserPosts(params.id),
    },
  ]);

  return (
    <HydrationBoundary state={dehydratedState}>
      <UserProfile userId={params.id} />
    </HydrationBoundary>
  );
}
```

---

### 6. 혼합 전략 (권장)

Server Component와 Client Component를 적절히 조합:

```typescript
// app/posts/[id]/page.tsx
import { dehydrate, HydrationBoundary, QueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/lib/react-query/query-keys';
import { fetchPost } from '@/lib/api/posts';
import PostContent from './PostContent';
import PostComments from './PostComments';
import RelatedPosts from './RelatedPosts';

export default async function PostPage({ params }: { params: { id: string } }) {
  const queryClient = new QueryClient();

  // 중요한 콘텐츠만 프리패치
  await queryClient.prefetchQuery({
    queryKey: queryKeys.posts.detail(params.id),
    queryFn: () => fetchPost(params.id),
  });

  return (
    <div>
      {/* 프리패치된 데이터 사용 (SSR) */}
      <HydrationBoundary state={dehydrate(queryClient)}>
        <PostContent postId={params.id} />
      </HydrationBoundary>

      {/* 클라이언트에서 lazy 로딩 */}
      <PostComments postId={params.id} />
      <RelatedPosts postId={params.id} />
    </div>
  );
}
```

---

### 7. 에러 핸들링

```typescript
// app/users/[id]/page.tsx
import { notFound } from 'next/navigation';
import { dehydrate, HydrationBoundary, QueryClient } from '@tanstack/react-query';
import { queryKeys } from '@/lib/react-query/query-keys';
import { fetchUser } from '@/lib/api/users';
import UserProfile from './UserProfile';

export default async function UserPage({ params }: { params: { id: string } }) {
  const queryClient = new QueryClient();

  try {
    await queryClient.prefetchQuery({
      queryKey: queryKeys.users.detail(params.id),
      queryFn: () => fetchUser(params.id),
    });
  } catch (error) {
    // 404 처리
    if (error.response?.status === 404) {
      notFound();
    }
    throw error;
  }

  return (
    <HydrationBoundary state={dehydrate(queryClient)}>
      <UserProfile userId={params.id} />
    </HydrationBoundary>
  );
}
```

---

### 8. 캐시 전략 설정

```typescript
// Server Component에서 QueryClient 생성 시 옵션 지정
import { QueryClient } from '@tanstack/react-query';

export default async function Page() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        // Server에서는 staleTime을 무한대로 설정 (한 번만 fetch)
        staleTime: Infinity,
        
        // 에러 시 재시도 안 함 (SSR에서는 불필요)
        retry: false,
      },
    },
  });

  // ... prefetch logic
}
```

---

### 패턴 비교

| 패턴 | 장점 | 단점 | 사용 케이스 |
|------|------|------|------------|
| **Hydration 패턴** | SEO 최적화, 초기 로딩 빠름 | 설정 복잡 | 중요한 페이지, 공개 콘텐츠 |
| **Client Only** | 간단한 구현 | SEO 불리, 로딩 시간 | 대시보드, 인증 필요 페이지 |
| **Props 전달** | 가장 간단 | React Query 장점 상실 | 정적 데이터 |
| **혼합 전략** | 유연성, 최적 성능 | 설계 필요 | 대부분의 경우 권장 |

---

### 권장 전략

```
┌─────────────────────────────────────────────┐
│            페이지 타입별 전략                  │
├─────────────────────────────────────────────┤
│                                               │
│  📄 공개 콘텐츠 페이지 (블로그, 상품 상세)     │
│  → Hydration 패턴 (SEO 최적화)                │
│                                               │
│  🔐 인증 필요 페이지 (대시보드, 설정)          │
│  → Client Component + useQuery                │
│                                               │
│  🔍 검색/필터 페이지                           │
│  → 혼합: 초기 결과는 Hydration, 필터는 Client │
│                                               │
│  📊 실시간 데이터 (알림, 채팅)                 │
│  → Client Component + useQuery + Polling      │
│                                               │
└─────────────────────────────────────────────┘
```

---

## 구현 단계

### Phase 1: 설치 및 기본 설정 ✅
```bash
pnpm add @tanstack/react-query @tanstack/react-query-devtools
pnpm add axios  # 또는 기존 fetch 사용
```

### Phase 2: QueryClient 설정
1. `lib/react-query/query-client.ts` 생성
2. `lib/react-query/query-provider.tsx` 생성
3. `app/layout.tsx`에 Provider 추가

### Phase 3: API Client 설정
1. `lib/api/client.ts` - Axios/Fetch 인스턴스
2. `lib/api/interceptors.ts` - 토큰 주입 로직
3. Zustand와 연동 (토큰 가져오기)

### Phase 4: Query Keys 정의
1. `lib/react-query/query-keys.ts` - Factory 패턴

### Phase 5: Custom Hooks 작성
1. Query Hooks (`hooks/queries/`)
2. Mutation Hooks (`hooks/mutations/`)

### Phase 6: 통합 및 최적화
1. 기존 API 호출을 React Query로 마이그레이션
2. DevTools로 캐싱 동작 확인
3. 성능 최적화 (staleTime, gcTime 조정)

---

## 주의사항

### 1. **Next.js App Router SSR**
```typescript
// Server Component에서는 사용 불가
// Client Component에서만 사용
'use client';
```

### 2. **Hydration 에러 방지**
```typescript
// 클라이언트에서만 실행
const { data } = useQuery({
  queryKey: ['user'],
  queryFn: fetchUser,
  enabled: typeof window !== 'undefined', // SSR에서 실행 방지
});
```

### 3. **메모리 누수 방지**
```typescript
// gcTime 설정으로 미사용 캐시 자동 제거
gcTime: 1000 * 60 * 10, // 10분
```

### 4. **토큰 갱신**
```typescript
// 401 에러 시 토큰 갱신 로직
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      // 토큰 갱신 시도
      const newToken = await refreshToken();
      if (newToken) {
        // 재시도
        return apiClient.request(error.config);
      }
    }
    return Promise.reject(error);
  }
);
```

---

## 프리패치 최적화 전략

### ⚠️ 중요: 프리패치 데이터 범위 제한

Server Component에서 프리패치할 데이터는 **필수 요약 데이터(Summary Data)로 한정**해야 합니다.

### 문제점: 과도한 프리패치

```typescript
// ❌ 나쁜 예: 모든 데이터를 프리패치
export default async function DashboardPage() {
  const queryClient = new QueryClient();
  
  await Promise.all([
    queryClient.prefetchQuery({ queryKey: ['user'], queryFn: fetchUser }),
    queryClient.prefetchQuery({ queryKey: ['posts'], queryFn: fetchPosts }),         // 100개 게시물
    queryClient.prefetchQuery({ queryKey: ['comments'], queryFn: fetchComments }),   // 500개 댓글
    queryClient.prefetchQuery({ queryKey: ['analytics'], queryFn: fetchAnalytics }), // 차트 데이터
    queryClient.prefetchQuery({ queryKey: ['notifications'], queryFn: fetchNotifications }),
    queryClient.prefetchQuery({ queryKey: ['settings'], queryFn: fetchSettings }),
  ]);

  // 문제점:
  // - TTFB(Time To First Byte) 증가
  // - 초기 HTML 크기 증가
  // - 사용자가 보지 않을 데이터까지 로딩
  // - 서버 부하 증가
}
```

### 권장: Progressive Loading 패턴

```typescript
// ✅ 좋은 예: 필수 요약 데이터만 프리패치
export default async function DashboardPage() {
  const queryClient = new QueryClient();
  
  // 1. 필수 요약 데이터만 서버에서 프리패치
  await queryClient.prefetchQuery({
    queryKey: ['dashboard-summary'],
    queryFn: async () => {
      const summary = await fetchDashboardSummary();
      return {
        totalUsers: summary.totalUsers,
        activeUsers: summary.activeUsers,
        revenue: summary.revenue,
        lastUpdated: summary.lastUpdated,
      };
    },
  });

  return (
    <HydrationBoundary state={dehydrate(queryClient)}>
      {/* 요약 데이터 (SSR) */}
      <DashboardSummary />
      
      {/* 상세 데이터 (CSR - 클라이언트에서 로딩) */}
      <Suspense fallback={<ChartsSkeleton />}>
        <DashboardCharts />
      </Suspense>
      
      <Suspense fallback={<PostsSkeleton />}>
        <RecentPosts />
      </Suspense>
    </HydrationBoundary>
  );
}
```

```typescript
// DashboardCharts.tsx (Client Component)
'use client';

import { useQuery } from '@tanstack/react-query';
import { useInView } from 'react-intersection-observer';

export default function DashboardCharts() {
  const { ref, inView } = useInView({ triggerOnce: true });
  
  // 화면에 보일 때만 데이터 로딩
  const { data, isLoading } = useQuery({
    queryKey: ['analytics'],
    queryFn: fetchAnalytics,
    enabled: inView, // Lazy loading
  });

  return (
    <div ref={ref}>
      {isLoading ? <ChartsSkeleton /> : <Charts data={data} />}
    </div>
  );
}
```

### 프리패치 우선순위 가이드

| 우선순위 | 데이터 유형 | 전략 | 예시 |
|---------|-----------|------|------|
| **High** | Above the Fold | Server 프리패치 | 요약 통계, 제목, 썸네일 |
| **Medium** | Below the Fold | Client + Intersection Observer | 차트, 댓글, 상세 내용 |
| **Low** | 사용자 액션 필요 | Client + 이벤트 트리거 | 모달 데이터, 필터 결과 |
| **On-Demand** | 탭/드롭다운 | Client + Prefetch on Hover | 프로필 상세, 추가 정보 |

### 실전 예시: 블로그 게시물 페이지

```typescript
// app/posts/[id]/page.tsx
export default async function PostPage({ params }: { params: { id: string } }) {
  const dehydratedState = await prefetchQuery(
    queryKeys.posts.detail(params.id),
    async () => {
      const post = await fetchPost(params.id);
      // 필수 정보만 반환
      return {
        id: post.id,
        title: post.title,
        content: post.content,
        author: post.author,
        publishedAt: post.publishedAt,
        // 댓글은 프리패치 제외 (클라이언트에서 로딩)
      };
    }
  );

  return (
    <HydrationBoundary state={dehydratedState}>
      <PostContent postId={params.id} />      {/* SSR */}
      <PostComments postId={params.id} />     {/* CSR */}
      <RelatedPosts postId={params.id} />     {/* CSR + Lazy */}
    </HydrationBoundary>
  );
}
```

---

## 데이터 직렬화 문제 해결

### ⚠️ 중요: Date 객체 직렬화 이슈

Server Component에서 `dehydrate()`를 사용하면 Date 객체가 **JSON 문자열**로 변환됩니다.

### 문제 상황

```typescript
// Server Component
const user = await fetchUser();
console.log(user.createdAt); // Date 객체: 2024-01-01T00:00:00.000Z

// dehydrate 과정
const dehydratedState = dehydrate(queryClient);
// → JSON.stringify 내부 호출
// → Date 객체가 string으로 변환

// Client Component
const { data: user } = useQuery({ ... });
console.log(user.createdAt instanceof Date);  // false ❌
console.log(typeof user.createdAt);           // "string"
user.createdAt.getTime();                     // TypeError! ❌
```

### 해결 방법 1: superjson 사용 (권장) ⭐

```bash
pnpm add superjson
```

```typescript
// lib/react-query/prefetch-helpers.ts
import superjson from 'superjson';
import { QueryClient, dehydrate } from '@tanstack/react-query';

export async function prefetchQueryWithSuperjson(
  queryKey: readonly unknown[],
  queryFn: () => Promise<unknown>
) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { staleTime: Infinity, retry: false },
    },
  });

  await queryClient.prefetchQuery({ queryKey, queryFn });

  // superjson으로 직렬화 (Date, Map, Set 등 보존)
  return superjson.serialize(dehydrate(queryClient));
}
```

```typescript
// lib/react-query/query-provider.tsx
'use client';

import superjson from 'superjson';
import { HydrationBoundary } from '@tanstack/react-query';

export function SuperjsonHydrationBoundary({ 
  state, 
  children 
}: { 
  state: any; 
  children: React.ReactNode;
}) {
  // 역직렬화
  const dehydratedState = superjson.deserialize(state);
  
  return (
    <HydrationBoundary state={dehydratedState}>
      {children}
    </HydrationBoundary>
  );
}
```

```typescript
// app/users/[id]/page.tsx
import { SuperjsonHydrationBoundary } from '@/lib/react-query/query-provider';
import { prefetchQueryWithSuperjson } from '@/lib/react-query/prefetch-helpers';

export default async function UserPage({ params }) {
  const state = await prefetchQueryWithSuperjson(
    ['user', params.id],
    () => fetchUser(params.id)
  );

  return (
    <SuperjsonHydrationBoundary state={state}>
      <UserProfile userId={params.id} />
    </SuperjsonHydrationBoundary>
  );
}
```

### 해결 방법 2: 명시적 타입 변환

```typescript
// types/api.ts
export interface UserApiResponse {
  id: string;
  name: string;
  email: string;
  createdAt: string; // ISO 8601 string
}

export interface User {
  id: string;
  name: string;
  email: string;
  createdAt: Date; // Date 객체
}

// utils/transformers.ts
export function transformUser(api: UserApiResponse): User {
  return {
    ...api,
    createdAt: new Date(api.createdAt),
  };
}
```

```typescript
// hooks/queries/useUserQuery.ts
import { useQuery } from '@tanstack/react-query';
import { transformUser } from '@/utils/transformers';

export function useUserQuery(userId: string) {
  return useQuery({
    queryKey: ['user', userId],
    queryFn: async () => {
      const response = await fetchUser(userId);
      return transformUser(response); // Date 변환
    },
  });
}
```

### 해결 방법 3: 서버에서 ISO 문자열로 직렬화

```typescript
// Server Component에서 명시적으로 문자열 변환
export default async function PostPage({ params }) {
  const queryClient = new QueryClient();
  
  await queryClient.prefetchQuery({
    queryKey: ['post', params.id],
    queryFn: async () => {
      const post = await fetchPost(params.id);
      
      // Date를 ISO string으로 명시적 변환
      return {
        ...post,
        publishedAt: post.publishedAt.toISOString(),
        updatedAt: post.updatedAt.toISOString(),
      };
    },
  });

  // ...
}
```

```typescript
// Client Component에서 사용 시 변환
'use client';

export default function PostContent({ postId }) {
  const { data } = useQuery({
    queryKey: ['post', postId],
    queryFn: fetchPost,
    select: (data) => ({
      ...data,
      publishedAt: new Date(data.publishedAt),
      updatedAt: new Date(data.updatedAt),
    }),
  });
  
  // 이제 Date 객체로 사용 가능
  console.log(data.publishedAt.getTime()); // ✅ 정상 동작
}
```

### 해결 방법 4: 유틸리티 함수로 자동 변환

```typescript
// utils/date-helpers.ts
export function parseApiDates<T>(data: T): T {
  if (data === null || data === undefined) return data;
  
  if (typeof data === 'string' && /^\d{4}-\d{2}-\d{2}T/.test(data)) {
    return new Date(data) as any;
  }
  
  if (Array.isArray(data)) {
    return data.map(parseApiDates) as any;
  }
  
  if (typeof data === 'object') {
    return Object.fromEntries(
      Object.entries(data).map(([key, value]) => [key, parseApiDates(value)])
    ) as T;
  }
  
  return data;
}
```

```typescript
// hooks/queries/useUserQuery.ts
import { parseApiDates } from '@/utils/date-helpers';

export function useUserQuery(userId: string) {
  return useQuery({
    queryKey: ['user', userId],
    queryFn: async () => {
      const response = await fetchUser(userId);
      return parseApiDates(response); // 자동 변환
    },
  });
}
```

### 권장 방법 비교

| 방법 | 장점 | 단점 | 추천 |
|------|------|------|------|
| **superjson** | 자동 처리, Date/Map/Set 지원 | 의존성 추가, 번들 증가 | ⭐⭐⭐ |
| **명시적 변환** | 타입 안전, 직관적 | 보일러플레이트 | ⭐⭐ |
| **ISO 문자열** | 간단, 명확한 타입 | 수동 변환 필요 | ⭐⭐⭐ |
| **유틸리티 함수** | 자동화, 재사용 | 예상치 못한 변환 | ⭐ |

### 최종 권장 패턴

```typescript
// lib/react-query/prefetch-helpers.ts (개선)
import superjson from 'superjson';

export async function prefetchQuery<T>(
  queryKey: readonly unknown[],
  queryFn: () => Promise<T>,
  options?: { useSuperjson?: boolean }
) {
  const queryClient = new QueryClient();
  await queryClient.prefetchQuery({ queryKey, queryFn });
  
  const dehydrated = dehydrate(queryClient);
  
  // superjson 사용 여부 선택
  return options?.useSuperjson 
    ? superjson.serialize(dehydrated)
    : dehydrated;
}
```

```typescript
// app/users/[id]/page.tsx
export default async function UserPage({ params }) {
  // Date 객체가 있으면 superjson 사용
  const state = await prefetchQuery(
    ['user', params.id],
    () => fetchUser(params.id),
    { useSuperjson: true } // Date 자동 처리
  );

  return (
    <SuperjsonHydrationBoundary state={state}>
      <UserProfile userId={params.id} />
    </SuperjsonHydrationBoundary>
  );
}
```

---

## 참고 자료

- [TanStack Query 공식 문서](https://tanstack.com/query/latest)
- [React Query DevTools](https://tanstack.com/query/latest/docs/react/devtools)
- [Next.js Data Fetching](https://nextjs.org/docs/app/building-your-application/data-fetching)

---

## 결론

### Zustand + React Query 조합의 장점
- ✅ **명확한 책임 분리**: 클라이언트 상태 vs 서버 상태
- ✅ **자동 캐싱**: 중복 요청 제거, 성능 향상
- ✅ **개발자 경험**: DevTools, 타입 안전성
- ✅ **유지보수성**: 일관된 패턴, 확장 가능

### 권장 사용 패턴
| 상태 유형 | 사용 도구 | 예시 |
|----------|----------|------|
| 클라이언트 상태 | Zustand | 테마, 모달, 토큰 |
| 서버 상태 | React Query | 유저 정보, 게시물 |
| 폼 상태 | React Hook Form | 입력 필드 |

이 전략을 따라 구현하면 효율적이고 확장 가능한 데이터 패칭 시스템을 구축할 수 있습니다.

