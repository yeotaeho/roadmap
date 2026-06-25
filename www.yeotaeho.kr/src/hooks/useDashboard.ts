// 인사이트 대시보드 라이브 데이터 TanStack Query 훅
'use client';

import { useQuery } from '@tanstack/react-query';

import {
  fetchGapIssues,
  fetchOpportunities,
  fetchPulse,
  fetchSyncScores,
} from '@/lib/api/dashboard';

const STALE = 5 * 60 * 1000; // 5분

export function usePulse() {
  return useQuery({ queryKey: ['pulse'], queryFn: fetchPulse, staleTime: STALE, retry: 1 });
}

export function useGapIssues() {
  return useQuery({ queryKey: ['gap-issues'], queryFn: fetchGapIssues, staleTime: STALE, retry: 1 });
}

export function useOpportunities() {
  return useQuery({
    queryKey: ['chance-opportunities'],
    queryFn: fetchOpportunities,
    staleTime: STALE,
    retry: 1,
  });
}

export function useSyncScores(userId?: string) {
  return useQuery({
    queryKey: ['sync-scores', userId],
    queryFn: () => fetchSyncScores(userId as string),
    enabled: !!userId,
    staleTime: STALE,
    retry: 1,
  });
}
