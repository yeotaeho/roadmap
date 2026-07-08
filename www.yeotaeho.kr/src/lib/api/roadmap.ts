// Roadmap(전략 로드맵) 백엔드 서빙 API 클라이언트 — 여정 개요·성장 아카이브
import type { QuestTreeNode, SkillPillar } from '@/data/roadmapQuestMap';
import { getStore } from '@/store';
import { apiClient } from './client';

const RAW_API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export interface JourneyRoadmap {
  title: string;
  summary: string | null;
  skillPillars: SkillPillar[];
  bridgeKeywords: string[];
}

export interface JourneyResponse {
  roadmap: JourneyRoadmap | null;
  questTree: QuestTreeNode | null;
}

export async function fetchJourney(): Promise<JourneyResponse> {
  const { data } = await apiClient.get('/api/roadmap/journey');
  return { roadmap: data?.roadmap ?? null, questTree: data?.questTree ?? null };
}

export interface DayLog {
  completedQuestIds: string[];
  note: string;
}

export type ArchiveLogs = Record<string, DayLog>;

export async function fetchArchive(month: string): Promise<ArchiveLogs> {
  const { data } = await apiClient.get('/api/roadmap/archive', { params: { month } });
  return (data?.logs ?? {}) as ArchiveLogs;
}

export async function upsertArchiveDay(date: string, payload: DayLog): Promise<DayLog> {
  const { data } = await apiClient.put(`/api/roadmap/archive/${date}`, payload);
  return { completedQuestIds: data?.completedQuestIds ?? [], note: data?.note ?? '' };
}

export interface RefreshResult {
  source: 'llm' | 'template';
  questCount: number;
}

export async function refreshRoadmap(): Promise<RefreshResult> {
  const { data } = await apiClient.post('/api/roadmap/refine');
  return { source: data?.source ?? 'template', questCount: data?.quest_count ?? 0 };
}

// ── 로드맵 딥 에이전트 생성 런 (R-1) ──

export interface GenerationRun {
  runId: string;
  status: 'pending' | 'running' | 'succeeded' | 'failed';
  stage?: string | null;
  percent?: number | null;
  label?: string | null;
  error?: string | null;
  result?: { source?: string; questCount?: number } | null;
}

export interface GenerationStreamHandlers {
  onProgress: (e: { stage?: string; percent?: number; label?: string }) => void;
  onDone: (result?: unknown) => void;
  onError: (message: string) => void;
  onNone?: () => void;
}

export async function startGeneration(): Promise<{ started: boolean; alreadyRunning: boolean }> {
  const token = getStore().getState().token;
  const res = await fetch(`${RAW_API_BASE}/api/roadmap/generate`, {
    method: 'POST',
    headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    credentials: 'include',
  });
  if (res.status === 409) return { started: false, alreadyRunning: true };
  if (!res.ok) throw new Error(`generate failed: ${res.status}`);
  return { started: true, alreadyRunning: false };
}

export async function fetchGenerationStatus(): Promise<GenerationRun | null> {
  const token = getStore().getState().token;
  const res = await fetch(`${RAW_API_BASE}/api/roadmap/generate/status`, {
    headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    credentials: 'include',
  });
  if (!res.ok) return null;
  const data = await res.json();
  return data?.run ?? null;
}

export async function streamGeneration(
  handlers: GenerationStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const token = getStore().getState().token;
  const res = await fetch(`${RAW_API_BASE}/api/roadmap/generate/stream`, {
    headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    credentials: 'include',
    signal,
  });
  if (!res.ok || !res.body) throw new Error(`generation stream failed: ${res.status}`);
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split('\n\n');
    buffer = events.pop() ?? '';
    for (const evt of events) {
      const dataLine = evt.split('\n').find((l) => l.startsWith('data:'));
      if (!dataLine) continue;
      try {
        const obj = JSON.parse(dataLine.slice(5).trim()) as {
          type?: string; stage?: string; percent?: number; label?: string;
          message?: string; result?: unknown;
        };
        if (obj.type === 'progress' || obj.type === 'status') handlers.onProgress(obj);
        if (obj.type === 'done') handlers.onDone(obj.result);
        if (obj.type === 'error') handlers.onError(obj.message ?? '로드맵 생성에 실패했어요.');
        if (obj.type === 'none') handlers.onNone?.();
      } catch {
        /* 파싱 불가 조각 무시 */
      }
    }
  }
}
