// 노트 라이브 데이터 TanStack Query 훅 — 목록·상세·CRUD
'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  createNote,
  deleteNote,
  fetchNote,
  fetchNotes,
  NotePayload,
  updateNote,
} from '@/lib/api/notes';

const LIST_KEY = ['roadmap-notes'];

export function useNotesList(enabled = true) {
  return useQuery({
    queryKey: LIST_KEY,
    queryFn: fetchNotes,
    enabled,
    staleTime: 60 * 1000,
    retry: 1,
  });
}

export function useNote(id: number | null, enabled = true) {
  return useQuery({
    queryKey: ['roadmap-note', id],
    queryFn: () => fetchNote(id as number),
    enabled: enabled && id != null,
    staleTime: 30 * 1000,
    retry: 1,
  });
}

export function useCreateNote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: NotePayload & { title: string }) => createNote(payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: LIST_KEY }),
  });
}

export function useUpdateNote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: NotePayload }) =>
      updateNote(id, payload),
    onSuccess: (saved) => {
      qc.setQueryData(['roadmap-note', saved.id], saved);
      qc.invalidateQueries({ queryKey: LIST_KEY });
    },
  });
}

export function useDeleteNote() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => deleteNote(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: LIST_KEY }),
  });
}
