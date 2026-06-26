// 인사이트 대시보드 라이브 데이터 TanStack Query 훅
'use client';

import { useQuery } from '@tanstack/react-query';

import {
  fetchGapIssueDetail,
  fetchGapIssues,
  fetchOpportunities,
  fetchOpportunityDetail,
  fetchBriefing,
  fetchCausalChains,
  fetchCrossover,
  fetchPulse,
  fetchPulseHistory,
  fetchPulseOverview,
  fetchSyncScores,
  fetchTrendingKeywords,
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
    queryFn: fetchSyncScores,
    enabled: !!userId,
    staleTime: STALE,
    retry: 1,
  });
}

export function useGapIssueDetail(id: string) {
  return useQuery({
    queryKey: ['gap-issue', id],
    queryFn: () => fetchGapIssueDetail(id),
    enabled: !!id,
    staleTime: STALE,
    retry: 1,
  });
}

export function useOpportunityDetail(id: string) {
  return useQuery({
    queryKey: ['chance-opportunity', id],
    queryFn: () => fetchOpportunityDetail(id),
    enabled: !!id,
    staleTime: STALE,
    retry: 1,
  });
}

export function usePulseOverview() {
  return useQuery({
    queryKey: ['pulse-overview'],
    queryFn: fetchPulseOverview,
    staleTime: STALE,
    retry: 1,
  });
}

export function usePulseHistory(sector?: string) {
  return useQuery({
    queryKey: ['pulse-history', sector],
    queryFn: () => fetchPulseHistory(sector as string),
    enabled: !!sector,
    staleTime: STALE,
    retry: 1,
  });
}

export function useTrendingKeywords() {
  return useQuery({
    queryKey: ['trending-keywords'],
    queryFn: fetchTrendingKeywords,
    staleTime: STALE,
    retry: 1,
  });
}

export function useBriefing() {
  return useQuery({
    queryKey: ['briefing'],
    queryFn: fetchBriefing,
    staleTime: STALE,
    retry: 1,
  });
}

export function useCrossover() {
  return useQuery({
    queryKey: ['crossover'],
    queryFn: fetchCrossover,
    staleTime: STALE,
    retry: 1,
  });
}

export function useCausalChains() {
  return useQuery({
    queryKey: ['causal-chains'],
    queryFn: fetchCausalChains,
    staleTime: STALE,
    retry: 1,
  });
}
