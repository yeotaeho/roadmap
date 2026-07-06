// 플래너 라이브 데이터 TanStack Query 훅 — 보드·스프린트·태스크·분해
'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  createSprint,
  createTask,
  decomposeQuest,
  deleteSprint,
  deleteTask,
  fetchPlannerBoard,
  patchSprint,
  patchTask,
  reorderTasks,
  SprintCreatePayload,
  SprintPatchPayload,
  TaskCreatePayload,
  TaskPatchPayload,
} from '@/lib/api/planner';

const KEY = ['roadmap-planner'];
const STALE = 60 * 1000; // 1분 — 편집 빈도가 높은 화면

export function usePlannerBoard(enabled = true) {
  return useQuery({
    queryKey: KEY,
    queryFn: fetchPlannerBoard,
    enabled,
    staleTime: STALE,
    retry: 1,
  });
}

function useInvalidateBoard() {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ queryKey: KEY });
}

export function useCreateSprint() {
  const invalidate = useInvalidateBoard();
  return useMutation({
    mutationFn: (payload: SprintCreatePayload) => createSprint(payload),
    onSuccess: invalidate,
  });
}

export function usePatchSprint() {
  const invalidate = useInvalidateBoard();
  return useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: SprintPatchPayload }) =>
      patchSprint(id, payload),
    onSuccess: invalidate,
  });
}

export function useDeleteSprint() {
  const invalidate = useInvalidateBoard();
  return useMutation({
    mutationFn: (id: number) => deleteSprint(id),
    onSuccess: invalidate,
  });
}

export function useCreateTask() {
  const invalidate = useInvalidateBoard();
  return useMutation({
    mutationFn: (payload: TaskCreatePayload) => createTask(payload),
    onSuccess: invalidate,
  });
}

export function usePatchTask() {
  const invalidate = useInvalidateBoard();
  return useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: TaskPatchPayload }) =>
      patchTask(id, payload),
    onSuccess: invalidate,
  });
}

export function useDeleteTask() {
  const invalidate = useInvalidateBoard();
  return useMutation({
    mutationFn: (id: number) => deleteTask(id),
    onSuccess: invalidate,
  });
}

export function useReorderTasks() {
  const invalidate = useInvalidateBoard();
  return useMutation({
    mutationFn: ({ sprintId, taskIds }: { sprintId: number | null; taskIds: number[] }) =>
      reorderTasks(sprintId, taskIds),
    // 드래그는 로컬 state 선반영(BoardView) — 실패 시에만 서버 재동기화
    onError: invalidate,
  });
}

export function useDecomposeQuest() {
  const invalidate = useInvalidateBoard();
  return useMutation({
    mutationFn: (questKey: string) => decomposeQuest(questKey),
    onSuccess: invalidate,
  });
}
