// 전략 로드맵 라이브 데이터 TanStack Query 훅 — 여정·아카이브
'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useCallback, useEffect, useRef, useState } from 'react';

import {
  ArchiveLogs,
  DayLog,
  fetchArchive,
  fetchGenerationStatus,
  fetchJourney,
  GenerationRun,
  refreshRoadmap,
  startGeneration,
  streamGeneration,
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

export interface GenerationView {
  running: boolean;
  stage?: string | null;
  percent?: number | null;
  label?: string | null;
  error?: string | null;
}

/** 생성 런 상태 — 탭 진입 시 status 1회 조회, running 이면 SSE 구독으로 승격. */
export function useRoadmapGeneration(loggedIn: boolean) {
  const qc = useQueryClient();
  const [view, setView] = useState<GenerationView>({ running: false });
  const abortRef = useRef<AbortController | null>(null);

  const finish = useCallback(
    (error?: string) => {
      abortRef.current?.abort();
      abortRef.current = null;
      setView({ running: false, error: error ?? null });
      if (!error) {
        qc.invalidateQueries({ queryKey: ['roadmap-journey'] });
        qc.invalidateQueries({ queryKey: ['roadmap-planner'] });
      }
    },
    [qc],
  );

  const subscribe = useCallback(() => {
    if (abortRef.current) return;
    const ac = new AbortController();
    abortRef.current = ac;
    streamGeneration(
      {
        onProgress: (e) =>
          setView({ running: true, stage: e.stage, percent: e.percent, label: e.label }),
        onDone: () => finish(),
        onError: (m) => finish(m),
        onNone: () => finish(),
      },
      ac.signal,
    ).catch(() => {
      // 스트림 자체 실패 — 폴링 폴백 없이 조용히 종료(status 재조회로 복구 가능).
      if (abortRef.current === ac) finish();
    });
  }, [finish]);

  useEffect(() => {
    if (!loggedIn) return;
    let cancelled = false;
    fetchGenerationStatus().then((run: GenerationRun | null) => {
      if (cancelled || !run) return;
      if (run.status === 'running' || run.status === 'pending') {
        setView({ running: true, stage: run.stage, percent: run.percent, label: run.label });
        subscribe();
      }
    });
    return () => {
      cancelled = true;
      abortRef.current?.abort();
      abortRef.current = null;
    };
  }, [loggedIn, subscribe]);

  const start = useCallback(async () => {
    setView({ running: true, percent: 5, label: '생성 준비' });
    try {
      await startGeneration(); // 409 는 alreadyRunning — 그대로 구독.
      subscribe();
    } catch {
      finish('로드맵 생성을 시작하지 못했어요.');
    }
  }, [subscribe, finish]);

  return { view, start };
}
