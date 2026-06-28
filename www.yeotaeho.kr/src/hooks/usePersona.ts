// 페르소나(스킬·경험·학력) TanStack Query 훅
'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { fetchPersona, Persona, PersonaUpsert, upsertPersona } from '@/lib/api/persona';

const STALE = 5 * 60 * 1000; // 5분

export function usePersona(enabled = true) {
  return useQuery({
    queryKey: ['persona'],
    queryFn: fetchPersona,
    enabled,
    staleTime: STALE,
    retry: 1,
  });
}

export function useUpsertPersona() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: PersonaUpsert) => upsertPersona(payload),
    onSuccess: (saved: Persona) => {
      qc.setQueryData<Persona>(['persona'], saved);
      // 페르소나 변경 → 로드맵 재생성(Item 3) 반영 위해 무효화.
      qc.invalidateQueries({ queryKey: ['roadmap-journey'] });
    },
  });
}
