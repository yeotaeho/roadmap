// 페르소나(스킬·경험·학력) 백엔드 API 클라이언트 — user_intelligence 구조화 폼
import { apiClient } from './client';

export type SkillLevel = '입문' | '중급' | '심화';

export interface SkillItem {
  name: string;
  level: SkillLevel;
}

export interface ExperienceItem {
  title: string;
  description: string;
  period: string;
}

export interface EducationItem {
  school: string;
  major: string;
  degree: string;
  status: string;
}

export interface Persona {
  skills: SkillItem[];
  experiences: ExperienceItem[];
  education: EducationItem[];
  summary: string;
  source?: string | null;
}

const EMPTY: Persona = { skills: [], experiences: [], education: [], summary: '', source: null };

export async function fetchPersona(): Promise<Persona> {
  const { data } = await apiClient.get('/api/persona');
  return { ...EMPTY, ...(data?.persona ?? {}) };
}

export type PersonaUpsert = Omit<Persona, 'source'>;

export async function upsertPersona(payload: PersonaUpsert): Promise<Persona> {
  const { data } = await apiClient.put('/api/persona', payload);
  return { ...EMPTY, ...(data?.persona ?? {}) };
}
