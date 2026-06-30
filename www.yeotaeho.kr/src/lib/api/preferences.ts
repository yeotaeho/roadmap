// 성향·선호(disposition) API — /api/preferences 조회·저장

import { apiClient } from "./client";

export interface Preferences {
  workStyle: string | null;
  companySizePref: string | null;
  workTypePref: string | null;
  workValues: string[];
  source?: string | null;
}

const EMPTY: Preferences = {
  workStyle: null,
  companySizePref: null,
  workTypePref: null,
  workValues: [],
  source: null,
};

export async function fetchPreferences(): Promise<Preferences> {
  const { data } = await apiClient.get("/api/preferences");
  return { ...EMPTY, ...(data?.preferences ?? {}) };
}

export async function upsertPreferences(payload: Partial<Preferences>): Promise<Preferences> {
  const { data } = await apiClient.put("/api/preferences", payload);
  return { ...EMPTY, ...(data?.preferences ?? {}) };
}
