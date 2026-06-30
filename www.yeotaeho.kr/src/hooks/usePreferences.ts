// 성향·선호 조회·저장 훅
'use client';

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Preferences, fetchPreferences, upsertPreferences } from "@/lib/api/preferences";

export function usePreferences(enabled = true) {
  return useQuery({ queryKey: ["preferences"], queryFn: fetchPreferences, enabled, staleTime: 5 * 60 * 1000, retry: 1 });
}

export function useUpsertPreferences() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Partial<Preferences>) => upsertPreferences(payload),
    onSuccess: (saved: Preferences) => qc.setQueryData<Preferences>(["preferences"], saved),
  });
}
