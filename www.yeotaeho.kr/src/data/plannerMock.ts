/** 플래너·노트 비로그인 목업 — read-only 예시 데이터 (JourneyMap QUEST_TREE 와 questKey 정합) */

import type { PlannerBoard } from '@/lib/api/planner';
import type { NoteDetail, NoteListItem } from '@/lib/api/notes';

function isoOffset(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() + days);
  const p = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

export const PLANNER_MOCK: PlannerBoard = {
  sprints: [
    {
      id: 1, title: '이번 주 — 도메인 언어 익히기', goal: 'ESG 지표 지형도 완성',
      startDate: isoOffset(-1), endDate: isoOffset(5), state: 'active', position: 0,
    },
    {
      id: 2, title: '다음 주 — 스키마 초안', goal: null,
      startDate: isoOffset(6), endDate: isoOffset(12), state: 'planned', position: 1,
    },
  ],
  tasks: [
    { id: 11, sprintId: 1, questKey: 'q-esg-map', title: '공개 데이터 소스 목록화',
      description: '공공 API·리포트 소스 정리', status: 'done',
      startDate: isoOffset(-1), dueDate: isoOffset(1), estimatedDays: 2, position: 0, source: 'ai' },
    { id: 12, sprintId: 1, questKey: 'q-esg-map', title: '지표 용어집 초안',
      description: '핵심 지표 20개 한 장 정리', status: 'doing',
      startDate: isoOffset(1), dueDate: isoOffset(4), estimatedDays: 3, position: 1, source: 'ai' },
    { id: 13, sprintId: 2, questKey: 'q-carbon-schema', title: '탄소 데이터 엔티티 도출',
      description: '배출·감축 흐름 스케치', status: 'todo',
      startDate: isoOffset(6), dueDate: isoOffset(9), estimatedDays: 4, position: 0, source: 'user' },
    { id: 14, sprintId: null, questKey: 'q-pipeline-mini', title: 'FastAPI 미니 파이프라인 조사',
      description: '', status: 'todo',
      startDate: null, dueDate: null, estimatedDays: 5, position: 0, source: 'ai' },
    { id: 15, sprintId: null, questKey: null, title: '주간 회고 쓰기',
      description: '', status: 'todo',
      startDate: null, dueDate: null, estimatedDays: 1, position: 1, source: 'user' },
  ],
};

export const NOTES_MOCK_LIST: NoteListItem[] = [
  { id: 1, title: '탄소 스키마 아이디어', updatedAt: null, preview: 'scope3 경계를 어디서 끊을지 — [[지표 용어집]] 참고' },
  { id: 2, title: '지표 용어집', updatedAt: null, preview: 'Scope1/2/3, CSRD, 배출계수…' },
];

export const NOTES_MOCK_DETAIL: Record<number, NoteDetail> = {
  1: {
    id: 1, title: '탄소 스키마 아이디어',
    content: '## 경계 문제\n\nscope3 경계를 어디서 끊을지 고민. 자세한 용어는 [[지표 용어집]] 참고.\n\n- 엔티티: 배출원, 감축활동\n- 다음 행동: 미니 파이프라인과 연결',
    linkedTitles: ['지표 용어집'], taskId: null, questKey: 'q-carbon-schema',
    updatedAt: null, backlinks: [],
  },
  2: {
    id: 2, title: '지표 용어집',
    content: '# 용어집\n\n- **Scope1/2/3** — 직접·간접·가치사슬 배출\n- **CSRD** — EU 지속가능성 공시 지침',
    linkedTitles: [], taskId: null, questKey: 'q-esg-map',
    updatedAt: null, backlinks: [{ id: 1, title: '탄소 스키마 아이디어' }],
  },
};
