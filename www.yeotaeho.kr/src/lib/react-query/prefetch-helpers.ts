import { QueryClient, dehydrate, DehydratedState } from '@tanstack/react-query';
import superjson, { SuperJSONResult } from 'superjson';

interface PrefetchQuery {
  queryKey: readonly unknown[];
  queryFn: () => Promise<unknown>;
}

/**
 * Server Component용 QueryClient 생성
 */
export function createServerQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: Infinity, // Server에서는 stale 처리 안 함
        retry: false, // SSR에서는 재시도 불필요
      },
    },
  });
}

/**
 * 단일 쿼리 프리패치 (기본)
 * Date 객체가 없는 단순 데이터용
 */
export async function prefetchQuery<T>(
  queryKey: readonly unknown[],
  queryFn: () => Promise<T>
): Promise<DehydratedState> {
  const queryClient = createServerQueryClient();

  await queryClient.prefetchQuery({
    queryKey,
    queryFn,
  });

  return dehydrate(queryClient);
}

/**
 * 여러 쿼리를 병렬로 프리패치 (기본)
 * Date 객체가 없는 단순 데이터용
 */
export async function prefetchQueries(
  queries: PrefetchQuery[]
): Promise<DehydratedState> {
  const queryClient = createServerQueryClient();

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

/**
 * 단일 쿼리 프리패치 (superjson)
 * Date, Map, Set 등 복잡한 객체 포함 데이터용
 */
export async function prefetchQueryWithSuperjson<T>(
  queryKey: readonly unknown[],
  queryFn: () => Promise<T>
): Promise<SuperJSONResult> {
  const queryClient = createServerQueryClient();

  await queryClient.prefetchQuery({
    queryKey,
    queryFn,
  });

  // superjson으로 직렬화 (Date, Map, Set 등 보존)
  return superjson.serialize(dehydrate(queryClient));
}

/**
 * 여러 쿼리를 병렬로 프리패치 (superjson)
 * Date, Map, Set 등 복잡한 객체 포함 데이터용
 */
export async function prefetchQueriesWithSuperjson(
  queries: PrefetchQuery[]
): Promise<SuperJSONResult> {
  const queryClient = createServerQueryClient();

  await Promise.all(
    queries.map((query) =>
      queryClient.prefetchQuery({
        queryKey: query.queryKey,
        queryFn: query.queryFn,
      })
    )
  );

  return superjson.serialize(dehydrate(queryClient));
}

/**
 * 요약 데이터만 프리패치 (권장 패턴)
 * 상세 데이터는 클라이언트에서 로딩
 */
export async function prefetchSummaryData<T>(
  queryKey: readonly unknown[],
  queryFn: () => Promise<T>,
  options?: { useSuperjson?: boolean }
): Promise<DehydratedState | SuperJSONResult> {
  const queryClient = createServerQueryClient();

  await queryClient.prefetchQuery({
    queryKey,
    queryFn,
  });

  const dehydrated = dehydrate(queryClient);

  return options?.useSuperjson
    ? superjson.serialize(dehydrated)
    : dehydrated;
}
