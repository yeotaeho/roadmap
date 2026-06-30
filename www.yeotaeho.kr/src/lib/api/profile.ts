// 기본정보(데모그래픽) API — /api/user/profile 조회·저장

import { apiClient } from "./client";

export interface BasicProfile {
  birthYear: number | null;
  gender: string | null;
  region: string | null;
  currentStatus: string | null;
  educationLevel: string | null;
  source?: string | null;
}

const EMPTY: BasicProfile = {
  birthYear: null,
  gender: null,
  region: null,
  currentStatus: null,
  educationLevel: null,
  source: null,
};

export async function fetchProfile(): Promise<BasicProfile> {
  const { data } = await apiClient.get("/api/user/profile");
  return { ...EMPTY, ...(data?.profile ?? {}) };
}

export async function upsertProfile(payload: Partial<BasicProfile>): Promise<BasicProfile> {
  const { data } = await apiClient.put("/api/user/profile", payload);
  return { ...EMPTY, ...(data?.profile ?? {}) };
}
