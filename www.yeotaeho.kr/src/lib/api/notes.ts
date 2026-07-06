// 로드맵 노트 백엔드 API 클라이언트 — 목록·상세(백링크)·CRUD
import { apiClient } from './client';

export interface NoteListItem {
  id: number;
  title: string;
  updatedAt: string | null;
  preview: string;
}

export interface NoteDetail {
  id: number;
  title: string;
  content: string;
  linkedTitles: string[];
  taskId: number | null;
  questKey: string | null;
  updatedAt: string | null;
  backlinks: { id: number; title: string }[];
}

export async function fetchNotes(): Promise<NoteListItem[]> {
  const { data } = await apiClient.get('/api/roadmap/notes');
  return data?.notes ?? [];
}

export async function fetchNote(id: number): Promise<NoteDetail> {
  const { data } = await apiClient.get(`/api/roadmap/notes/${id}`);
  return data.note as NoteDetail;
}

export interface NotePayload {
  title?: string;
  content?: string;
  taskId?: number | null;
  questKey?: string | null;
}

export async function createNote(payload: NotePayload & { title: string }): Promise<NoteDetail> {
  const { data } = await apiClient.post('/api/roadmap/notes', payload);
  return data.note as NoteDetail;
}

export async function updateNote(id: number, payload: NotePayload): Promise<NoteDetail> {
  const { data } = await apiClient.put(`/api/roadmap/notes/${id}`, payload);
  return data.note as NoteDetail;
}

export async function deleteNote(id: number): Promise<void> {
  await apiClient.delete(`/api/roadmap/notes/${id}`);
}
