// 플래너(WBS) 백엔드 API 클라이언트 — 보드·스프린트·태스크·AI 분해
import { apiClient } from './client';

export type SprintState = 'planned' | 'active' | 'done';
export type TaskStatus = 'todo' | 'doing' | 'done';

export interface Sprint {
  id: number;
  title: string;
  goal: string | null;
  startDate: string;
  endDate: string;
  state: SprintState;
  position: number;
}

export interface PlannerTask {
  id: number;
  sprintId: number | null; // null = 백로그
  questKey: string | null;
  title: string;
  description: string;
  status: TaskStatus;
  startDate: string | null;
  dueDate: string | null;
  estimatedDays: number | null;
  position: number;
  source: 'user' | 'ai';
}

export interface PlannerBoard {
  sprints: Sprint[];
  tasks: PlannerTask[];
}

export async function fetchPlannerBoard(): Promise<PlannerBoard> {
  const { data } = await apiClient.get('/api/roadmap/planner');
  return { sprints: data?.sprints ?? [], tasks: data?.tasks ?? [] };
}

export interface SprintCreatePayload {
  title: string;
  goal?: string | null;
  startDate: string;
  endDate: string;
}

export async function createSprint(payload: SprintCreatePayload): Promise<Sprint> {
  const { data } = await apiClient.post('/api/roadmap/planner/sprints', payload);
  return data.sprint as Sprint;
}

export type SprintPatchPayload = Partial<
  Pick<Sprint, 'title' | 'goal' | 'startDate' | 'endDate' | 'state' | 'position'>
>;

export async function patchSprint(id: number, payload: SprintPatchPayload): Promise<void> {
  await apiClient.patch(`/api/roadmap/planner/sprints/${id}`, payload);
}

export async function deleteSprint(id: number): Promise<void> {
  await apiClient.delete(`/api/roadmap/planner/sprints/${id}`);
}

export interface TaskCreatePayload {
  title: string;
  description?: string | null;
  sprintId?: number | null;
  questKey?: string | null;
  startDate?: string | null;
  dueDate?: string | null;
  estimatedDays?: number | null;
}

export async function createTask(payload: TaskCreatePayload): Promise<PlannerTask> {
  const { data } = await apiClient.post('/api/roadmap/planner/tasks', payload);
  return data.task as PlannerTask;
}

export type TaskPatchPayload = Partial<
  Pick<
    PlannerTask,
    | 'title' | 'description' | 'sprintId' | 'questKey' | 'status'
    | 'startDate' | 'dueDate' | 'estimatedDays' | 'position'
  >
>;

export async function patchTask(id: number, payload: TaskPatchPayload): Promise<void> {
  await apiClient.patch(`/api/roadmap/planner/tasks/${id}`, payload);
}

export async function deleteTask(id: number): Promise<void> {
  await apiClient.delete(`/api/roadmap/planner/tasks/${id}`);
}

export async function reorderTasks(
  sprintId: number | null,
  taskIds: number[],
): Promise<void> {
  await apiClient.post('/api/roadmap/planner/tasks/reorder', { sprintId, taskIds });
}

export interface DecomposeResult {
  source: 'llm' | 'template';
  tasks: PlannerTask[];
}

export async function decomposeQuest(questKey: string): Promise<DecomposeResult> {
  const { data } = await apiClient.post('/api/roadmap/planner/decompose', { questKey });
  return { source: data?.source ?? 'template', tasks: data?.tasks ?? [] };
}
