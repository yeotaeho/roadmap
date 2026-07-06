"use client";

// 플래너 탭 — 보드/타임라인 토글 셸 + 데이터 로드·목업 폴백·생성/편집 다이얼로그

import { KanbanSquare, X } from "lucide-react";
import { useMemo, useState } from "react";
import { PLANNER_MOCK } from "@/data/plannerMock";
import { flattenQuestTitles, QUEST_TREE } from "@/data/roadmapQuestMap";
import { useJourney } from "@/hooks/useRoadmap";
import {
  useCreateSprint,
  useCreateTask,
  useDeleteSprint,
  useDeleteTask,
  usePatchTask,
  usePlannerBoard,
  useReorderTasks,
} from "@/hooks/usePlanner";
import type { PlannerTask, TaskStatus } from "@/lib/api/planner";
import { useStore } from "@/store";
import { BoardView } from "./BoardView";
import { TimelineView } from "./TimelineView";

type PlannerView = "board" | "timeline";

function isoToday(offset = 0): string {
  const d = new Date();
  d.setDate(d.getDate() + offset);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

export function PlannerTab() {
  const profile = useStore((s) => s.profile);
  const enabled = !!profile?.id;
  const { data, isLoading } = usePlannerBoard(enabled);
  const { data: journey } = useJourney(enabled);
  const board = enabled && data ? data : PLANNER_MOCK;
  const isLive = enabled && Boolean(data);

  const [view, setView] = useState<PlannerView>("board");
  const [editing, setEditing] = useState<PlannerTask | null>(null);
  const [addingTo, setAddingTo] = useState<{ open: boolean; sprintId: number | null }>({
    open: false,
    sprintId: null,
  });
  const [addingSprint, setAddingSprint] = useState(false);

  const questTitles = useMemo(() => {
    const tree = journey?.questTree ?? QUEST_TREE;
    return new Map(flattenQuestTitles(tree).map((q) => [q.id, q.title]));
  }, [journey]);

  const createSprint = useCreateSprint();
  const deleteSprint = useDeleteSprint();
  const createTask = useCreateTask();
  const patchTask = usePatchTask();
  const deleteTask = useDeleteTask();
  const reorder = useReorderTasks();

  const handleMove = (sprintId: number | null, taskIds: number[]) => {
    if (!enabled) return;
    reorder.mutate({ sprintId, taskIds });
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="inline-flex items-center gap-2 text-lg font-bold text-slate-900 dark:text-slate-100">
            <KanbanSquare className="h-5 w-5 text-indigo-600" />
            플래너
          </h2>
          <p className="mt-0.5 text-xs text-slate-600 dark:text-slate-400">
            퀘스트를 실행 태스크로 쪼개고, 스프린트로 묶어 일정을 잡습니다.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {!isLive && !isLoading ? (
            <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-500 dark:bg-slate-800 dark:text-slate-400">
              예시 데이터
            </span>
          ) : null}
          <div className="flex rounded-xl border border-slate-200 p-0.5 dark:border-slate-700">
            {(["board", "timeline"] as const).map((v) => (
              <button
                key={v}
                type="button"
                onClick={() => setView(v)}
                className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                  view === v
                    ? "bg-indigo-600 text-white shadow-sm"
                    : "text-slate-600 hover:text-indigo-600 dark:text-slate-400"
                }`}
              >
                {v === "board" ? "보드" : "타임라인"}
              </button>
            ))}
          </div>
        </div>
      </div>

      {view === "board" ? (
        <BoardView
          board={board}
          questTitles={questTitles}
          readOnly={!enabled}
          onMove={handleMove}
          onAddTask={(sprintId) => setAddingTo({ open: true, sprintId })}
          onAddSprint={() => setAddingSprint(true)}
          onDeleteSprint={(id) => {
            if (window.confirm("스프린트를 삭제할까요? 소속 태스크는 백로그로 돌아갑니다.")) {
              deleteSprint.mutate(id);
            }
          }}
          onTaskClick={(t) => setEditing(t)}
        />
      ) : (
        <TimelineView board={board} onTaskClick={(t) => setEditing(t)} />
      )}

      {/* 태스크 추가 폼 */}
      {addingTo.open ? (
        <TaskForm
          title="태스크 추가"
          onClose={() => setAddingTo({ open: false, sprintId: null })}
          onSubmit={(v) => {
            createTask.mutate({ ...v, sprintId: addingTo.sprintId });
            setAddingTo({ open: false, sprintId: null });
          }}
        />
      ) : null}

      {/* 스프린트 추가 폼 */}
      {addingSprint ? (
        <SprintForm
          onClose={() => setAddingSprint(false)}
          onSubmit={(v) => {
            createSprint.mutate(v);
            setAddingSprint(false);
          }}
        />
      ) : null}

      {/* 태스크 편집 패널 */}
      {editing ? (
        <TaskEditPanel
          task={editing}
          readOnly={!enabled}
          onClose={() => setEditing(null)}
          onSave={(fields) => {
            patchTask.mutate({ id: editing.id, payload: fields });
            setEditing(null);
          }}
          onDelete={() => {
            if (window.confirm("태스크를 삭제할까요?")) {
              deleteTask.mutate(editing.id);
              setEditing(null);
            }
          }}
        />
      ) : null}
    </div>
  );
}

function Modal({ children, onClose }: { children: React.ReactNode; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4">
      <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-5 shadow-xl dark:border-slate-700 dark:bg-slate-800">
        <div className="flex justify-end">
          <button type="button" onClick={onClose} aria-label="닫기">
            <X className="h-4 w-4 text-slate-400 hover:text-slate-600" />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

const inputCls =
  "mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 focus:border-indigo-300 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100";
const labelCls = "block text-xs font-semibold text-slate-600 dark:text-slate-400";
const primaryBtnCls =
  "mt-4 w-full rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-indigo-700 disabled:opacity-60";

function TaskForm({
  title,
  onClose,
  onSubmit,
}: {
  title: string;
  onClose: () => void;
  onSubmit: (v: { title: string; description: string }) => void;
}) {
  const [name, setName] = useState("");
  const [desc, setDesc] = useState("");
  return (
    <Modal onClose={onClose}>
      <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">{title}</h3>
      <label className={`${labelCls} mt-3`}>
        제목
        <input value={name} onChange={(e) => setName(e.target.value)} className={inputCls} />
      </label>
      <label className={`${labelCls} mt-3`}>
        설명 (선택)
        <textarea value={desc} onChange={(e) => setDesc(e.target.value)} rows={3} className={inputCls} />
      </label>
      <button
        type="button"
        disabled={!name.trim()}
        onClick={() => onSubmit({ title: name.trim(), description: desc.trim() })}
        className={primaryBtnCls}
      >
        추가
      </button>
    </Modal>
  );
}

function SprintForm({
  onClose,
  onSubmit,
}: {
  onClose: () => void;
  onSubmit: (v: { title: string; goal: string | null; startDate: string; endDate: string }) => void;
}) {
  const [name, setName] = useState("");
  const [goal, setGoal] = useState("");
  const [start, setStart] = useState(isoToday());
  const [end, setEnd] = useState(isoToday(6));
  const valid = name.trim().length > 0 && start <= end;
  return (
    <Modal onClose={onClose}>
      <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">스프린트 추가</h3>
      <label className={`${labelCls} mt-3`}>
        제목
        <input value={name} onChange={(e) => setName(e.target.value)} className={inputCls} placeholder="예: 1주차 — CS 기초" />
      </label>
      <label className={`${labelCls} mt-3`}>
        목표 (선택)
        <input value={goal} onChange={(e) => setGoal(e.target.value)} className={inputCls} />
      </label>
      <div className="mt-3 grid grid-cols-2 gap-2">
        <label className={labelCls}>
          시작일
          <input type="date" value={start} onChange={(e) => setStart(e.target.value)} className={inputCls} />
        </label>
        <label className={labelCls}>
          종료일
          <input type="date" value={end} onChange={(e) => setEnd(e.target.value)} className={inputCls} />
        </label>
      </div>
      <button
        type="button"
        disabled={!valid}
        onClick={() => onSubmit({ title: name.trim(), goal: goal.trim() || null, startDate: start, endDate: end })}
        className={primaryBtnCls}
      >
        추가
      </button>
    </Modal>
  );
}

function TaskEditPanel({
  task,
  readOnly,
  onClose,
  onSave,
  onDelete,
}: {
  task: PlannerTask;
  readOnly: boolean;
  onClose: () => void;
  onSave: (fields: { status: TaskStatus; startDate: string | null; dueDate: string | null }) => void;
  onDelete: () => void;
}) {
  const [status, setStatus] = useState<TaskStatus>(task.status);
  const [start, setStart] = useState(task.startDate ?? "");
  const [due, setDue] = useState(task.dueDate ?? "");
  return (
    <Modal onClose={onClose}>
      <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">{task.title}</h3>
      {task.description ? (
        <p className="mt-1 text-xs text-slate-600 dark:text-slate-400">{task.description}</p>
      ) : null}
      <label className={`${labelCls} mt-3`}>
        상태
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value as TaskStatus)}
          className={inputCls}
          disabled={readOnly}
        >
          <option value="todo">할 일</option>
          <option value="doing">진행 중</option>
          <option value="done">완료</option>
        </select>
      </label>
      <div className="mt-3 grid grid-cols-2 gap-2">
        <label className={labelCls}>
          시작일
          <input type="date" value={start} onChange={(e) => setStart(e.target.value)} className={inputCls} disabled={readOnly} />
        </label>
        <label className={labelCls}>
          마감일
          <input type="date" value={due} onChange={(e) => setDue(e.target.value)} className={inputCls} disabled={readOnly} />
        </label>
      </div>
      {!readOnly ? (
        <>
          <button
            type="button"
            onClick={() => onSave({ status, startDate: start || null, dueDate: due || null })}
            className={primaryBtnCls}
          >
            저장
          </button>
          <button
            type="button"
            onClick={onDelete}
            className="mt-2 w-full rounded-xl border border-rose-200 px-4 py-2 text-xs font-semibold text-rose-600 hover:bg-rose-50 dark:border-rose-900/40 dark:hover:bg-rose-900/15"
          >
            태스크 삭제
          </button>
        </>
      ) : (
        <p className="mt-4 text-center text-xs text-slate-400">로그인하면 편집할 수 있습니다.</p>
      )}
    </Modal>
  );
}
