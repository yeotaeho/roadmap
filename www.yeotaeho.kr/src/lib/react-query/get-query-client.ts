import { QueryClient, isServer } from '@tanstack/react-query';

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        // SSR에서는 staleTime을 설정하여 클라이언트에서 즉시 refetch 방지
        staleTime: 1000 * 60 * 5, // 5분
        gcTime: 1000 * 60 * 10, // 10분
        retry: 1,
        refetchOnWindowFocus: process.env.NODE_ENV === 'production',
        refetchOnMount: true,
        refetchOnReconnect: true,
      },
      mutations: {
        retry: 0,
      },
    },
  });
}

let browserQueryClient: QueryClient | undefined = undefined;

/**
 * Server/Client 환경에 따라 QueryClient를 반환
 * - Server: 매번 새로운 QueryClient 생성 (요청 간 데이터 공유 방지)
 * - Client: 싱글톤 패턴으로 하나의 QueryClient 재사용
 */
export function getQueryClient() {
  if (isServer) {
    // Server: 항상 새로운 QueryClient 생성
    return makeQueryClient();
  } else {
    // Browser: 싱글톤 패턴
    if (!browserQueryClient) {
      browserQueryClient = makeQueryClient();
    }
    return browserQueryClient;
  }
}

