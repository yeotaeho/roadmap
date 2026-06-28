// Roadmap(전략 로드맵) 백엔드 서빙 API 클라이언트 — 여정 개요·성장 아카이브
import type { QuestTreeNode, SkillPillar } from '@/data/roadmapQuestMap';
import { apiClient } from './client';

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
