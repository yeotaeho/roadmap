// 기본정보 조회·저장 훅
'use client';

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { BasicProfile, fetchProfile, upsertProfile } from "@/lib/api/profile";

export function useProfile(enabled = true) {
  return useQuery({ queryKey: ["profile"], queryFn: fetchProfile, enabled, staleTime: 5 * 60 * 1000, retry: 1 });
}

export function useUpsertProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Partial<BasicProfile>) => upsertProfile(payload),
    onSuccess: (saved: BasicProfile) => qc.setQueryData<BasicProfile>(["profile"], saved),
  });
}
