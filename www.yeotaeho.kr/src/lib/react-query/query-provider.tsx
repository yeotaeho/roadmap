'use client';

import { QueryClientProvider, HydrationBoundary, DehydratedState } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import superjson, { SuperJSONResult } from 'superjson';
import { getQueryClient } from './get-query-client';

/**
 * 기본 Query Provider
 */
export function QueryProvider({ children }: { children: React.ReactNode }) {
  const queryClient = getQueryClient();

  return (
    <QueryClientProvider client={queryClient}>
      {children}
      {process.env.NODE_ENV === 'development' && (
        <ReactQueryDevtools initialIsOpen={false} position="bottom" />
      )}
    </QueryClientProvider>
  );
}

/**
 * Superjson Hydration Boundary
 * Date, Map, Set 등 복잡한 객체가 포함된 데이터용
 */
export function SuperjsonHydrationBoundary({
  state,
  children,
}: {
  state: SuperJSONResult;
  children: React.ReactNode;
}) {
  // superjson으로 역직렬화 (Date 객체 복원)
  const dehydratedState = superjson.deserialize<DehydratedState>(state);

  return (
    <HydrationBoundary state={dehydratedState}>
      {children}
    </HydrationBoundary>
  );
}
