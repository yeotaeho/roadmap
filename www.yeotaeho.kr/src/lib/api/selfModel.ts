// AI 상담실 자기모델(RIASEC·서사·근거) 서빙 API 클라이언트
import { apiClient } from './client';

export interface SelfModelEvidence {
  dimension: string;
  polarity: string | null;
  content: string;
  confidence: number | null;
}

export interface RiasecScores {
  R: number; I: number; A: number; S: number; E: number; C: number;
}

export interface BigFiveScores {
  O: number; C: number; E: number; A: number; N: number;
}

export interface SelfModelLive {
  riasec: { scores?: RiasecScores; top_codes: string[] } | null;
  bigFive: { scores: BigFiveScores } | null;
  narrativeSummary: string | null;
  axisConfidence: Record<string, number> | null;
  axisSource: Record<string, string> | null;
  evidence: SelfModelEvidence[];
}

export async function fetchSelfModel(): Promise<SelfModelLive> {
  const { data } = await apiClient.get('/api/user/self-model');
  const m = data?.selfModel ?? {};
  return {
    riasec: m.riasec ?? null,
    bigFive: m.bigFive ?? null,
    narrativeSummary: m.narrativeSummary ?? null,
    axisConfidence: m.axisConfidence ?? null,
    axisSource: m.axisSource ?? null,
    evidence: Array.isArray(m.evidence) ? m.evidence : [],
  };
}

export type AxisLevel = "low" | "mid" | "high";

export interface SelfModelEdits {
  riasec?: { levels: Record<string, AxisLevel> } | "auto";
  big_five?: { levels: Record<string, AxisLevel> } | "auto";
  narrative?: string | "auto";
}

export async function updateSelfModel(edits: SelfModelEdits): Promise<SelfModelLive> {
  const { data } = await apiClient.put("/api/user/self-model", edits);
  const m = data?.selfModel ?? {};
  return {
    riasec: m.riasec ?? null,
    bigFive: m.bigFive ?? null,
    narrativeSummary: m.narrativeSummary ?? null,
    axisConfidence: m.axisConfidence ?? null,
    axisSource: m.axisSource ?? null,
    evidence: Array.isArray(m.evidence) ? m.evidence : [],
  };
}
