// 전략 로드맵 라이브 데이터 TanStack Query 훅 — 여정·아카이브
'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  ArchiveLogs,
  DayLog,
  fetchArchive,
  fetchJourney,
  refreshRoadmap,
  upsertArchiveDay,
} from '@/lib/api/roadmap';

const STALE = 5 * 60 * 1000; // 5분

export function useJourney(enabled = true) {
  return useQuery({
    queryKey: ['roadmap-journey'],
    queryFn: fetchJourney,
    enabled,
    staleTime: STALE,
    retry: 1,
  });
}

export function useArchive(month: string, enabled = true) {
  return useQuery({
    queryKey: ['roadmap-archive', month],
    queryFn: () => fetchArchive(month),
    enabled,
    staleTime: STALE,
    retry: 1,
  });
}

export function useRefreshRoadmap() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: refreshRoadmap,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['roadmap-journey'] });
    },
  });
}

export function useUpsertArchiveDay() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ date, payload }: { date: string; payload: DayLog }) =>
      upsertArchiveDay(date, payload),
    onSuccess: (saved, { date }) => {
      // 해당 월 캐시에 즉시 반영(낙관적 머지).
      const month = date.slice(0, 7);
      qc.setQueryData<ArchiveLogs>(['roadmap-archive', month], (prev) => ({
        ...(prev ?? {}),
        [date]: saved,
      }));
    },
  });
}
