"use client";

// 플래너 보드 뷰 — 백로그 + 스프린트 컬럼, dnd-kit 드래그 이동·정렬

import {
  DndContext,
  DragEndEvent,
  DragOverlay,
  DragStartEvent,
  PointerSensor,
  closestCorners,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import {
  SortableContext,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { Inbox, Plus, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { PlannerBoard, PlannerTask, Sprint } from "@/lib/api/planner";
import { TaskCard } from "./TaskCard";

// 컬럼 id 규약: 백로그 "backlog", 스프린트 "sprint-<id>"
const BACKLOG = "backlog";
const colId = (sprintId: number | null) => (sprintId == null ? BACKLOG : `sprint-${sprintId}`);
const parseCol = (id: string): number | null =>
  id === BACKLOG ? null : Number(id.replace("sprint-", ""));

function SortableTask({
  task,
  questTitle,
  disabled,
  onClick,
}: {
  task: PlannerTask;
  questTitle?: string;
  disabled: boolean;
  onClick?: () => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: String(task.id),
    disabled,
  });
  return (
    <div
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      className={isDragging ? "opacity-40" : ""}
      {...attributes}
      {...listeners}
    >
      <TaskCard task={task} questTitle={questTitle} onClick={onClick} />
    </div>
  );
}

function Column({
  id,
  title,
  subtitle,
  tasks,
  questTitles,
  readOnly,
  onAddTask,
  onDeleteSprint,
  onTaskClick,
  progress,
  headerExtra,
}: {
  id: string;
  title: string;
  subtitle?: string;
  tasks: PlannerTask[];
  questTitles: Map<string, string>;
  readOnly: boolean;
  onAddTask?: () => void;
  onDeleteSprint?: () => void;
  onTaskClick?: (t: PlannerTask) => void;
  progress?: number; // 0~100
  headerExtra?: React.ReactNode;
}) {
  return (
    <section className="flex w-72 shrink-0 flex-col rounded-2xl border border-slate-200 bg-[#F8FAFC] p-3 shadow-sm dark:border-slate-700 dark:bg-slate-900">
      <div className="flex items-start justify-between gap-2 px-1">
        <div>
          <h3 className="text-xs font-bold text-slate-900 dark:text-slate-100">{title}</h3>
          {subtitle ? (
            <p className="mt-0.5 text-[10px] text-slate-500 dark:text-slate-500">{subtitle}</p>
          ) : null}
        </div>
        <div className="flex items-center gap-1">
          {onAddTask ? (
            <button
              type="button"
              onClick={onAddTask}
              className="rounded-lg border border-slate-200 p-1 text-slate-500 hover:bg-white dark:border-slate-700 dark:text-slate-400 dark:hover:bg-slate-800"
              aria-label="태스크 추가"
            >
              <Plus className="h-3.5 w-3.5" />
            </button>
          ) : null}
          {onDeleteSprint ? (
            <button
              type="button"
              onClick={onDeleteSprint}
              className="rounded-lg border border-slate-200 p-1 text-slate-400 hover:bg-rose-50 hover:text-rose-600 dark:border-slate-700 dark:hover:bg-rose-900/20"
              aria-label="스프린트 삭제"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          ) : null}
        </div>
      </div>
      {headerExtra}
      {progress != null ? (
        <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700">
          <div
            className="h-full rounded-full bg-indigo-500 transition-all"
            style={{ width: `${progress}%` }}
          />
        </div>
      ) : null}
      <SortableContext
        id={id}
        items={tasks.map((t) => String(t.id))}
        strategy={verticalListSortingStrategy}
      >
        <div className="mt-3 flex min-h-[80px] flex-1 flex-col gap-2" data-column={id}>
          {tasks.map((t) => (
            <SortableTask
              key={t.id}
              task={t}
              questTitle={t.questKey ? questTitles.get(t.questKey) : undefined}
              disabled={readOnly}
              onClick={() => onTaskClick?.(t)}
            />
          ))}
          {tasks.length === 0 ? (
            <p className="rounded-xl border border-dashed border-slate-200 p-4 text-center text-[11px] text-slate-400 dark:border-slate-700">
              카드를 끌어다 놓으세요
            </p>
          ) : null}
        </div>
      </SortableContext>
    </section>
  );
}

export function BoardView({
  board,
  questTitles,
  readOnly,
  onMove,
  onAddTask,
  onAddSprint,
  onDeleteSprint,
  onTaskClick,
  decomposeSlot,
}: {
  board: PlannerBoard;
  questTitles: Map<string, string>;
  readOnly: boolean;
  /** 드래그 확정 — 대상 컬럼(sprintId)과 그 컬럼의 새 taskId 순서 */
  onMove: (sprintId: number | null, taskIds: number[]) => void;
  onAddTask: (sprintId: number | null) => void;
  onAddSprint: () => void;
  onDeleteSprint: (id: number) => void;
  onTaskClick: (t: PlannerTask) => void;
  decomposeSlot?: React.ReactNode;
}) {
  const [activeTask, setActiveTask] = useState<PlannerTask | null>(null);
  // 드래그 중 로컬 배치 상태 — 서버 확정 전 선반영
  const [local, setLocal] = useState<PlannerTask[] | null>(null);
  const tasks = local ?? board.tasks;

  // 서버 보드가 갱신되면 로컬 선반영을 해제(서버가 진실원). reorder 성공은 refetch가 없어 로컬 유지.
  useEffect(() => {
    setLocal(null);
  }, [board.tasks]);

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }));

  const byColumn = useMemo(() => {
    const m = new Map<string, PlannerTask[]>();
    m.set(BACKLOG, []);
    for (const s of board.sprints) m.set(colId(s.id), []);
    for (const t of tasks) {
      const key = colId(t.sprintId);
      if (!m.has(key)) m.set(key, []);
      m.get(key)!.push(t);
    }
    for (const list of m.values()) list.sort((a, b) => a.position - b.position || a.id - b.id);
    return m;
  }, [tasks, board.sprints]);

  const findColumnOf = (taskId: string): string | undefined => {
    for (const [cid, list] of byColumn) {
      if (list.some((t) => String(t.id) === taskId)) return cid;
    }
    return undefined;
  };

  const handleDragStart = (e: DragStartEvent) => {
    const t = tasks.find((x) => String(x.id) === String(e.active.id));
    setActiveTask(t ?? null);
  };

  const handleDragEnd = (e: DragEndEvent) => {
    setActiveTask(null);
    const { active, over } = e;
    if (!over) return;
    if (String(over.id) === String(active.id)) return;
    const fromCol = findColumnOf(String(active.id));
    // over 가 태스크면 그 태스크의 컬럼, 컬럼 컨테이너면 그대로
    const overIsColumn = String(over.id) === BACKLOG || String(over.id).startsWith("sprint-");
    const toCol = overIsColumn ? String(over.id) : findColumnOf(String(over.id));
    if (!fromCol || !toCol) return;

    const moved = tasks.find((t) => String(t.id) === String(active.id));
    if (!moved) return;

    const target = (byColumn.get(toCol) ?? []).filter((t) => t.id !== moved.id);
    let insertAt = target.length;
    if (!overIsColumn) {
      const idx = target.findIndex((t) => String(t.id) === String(over.id));
      if (idx >= 0) insertAt = idx;
    }
    target.splice(insertAt, 0, { ...moved, sprintId: parseCol(toCol) });

    // 로컬 선반영: 대상 컬럼만 position 재부여. 원본 컬럼의 갭은 의도적 — 정렬키(position, id)로 순서 안정, 다음 reorder 시 치유.
    const targetIds = new Set(target.map((t) => t.id));
    setLocal(
      tasks
        .filter((t) => !targetIds.has(t.id))
        .concat(target.map((t, i) => ({ ...t, position: i }))),
    );
    onMove(parseCol(toCol), target.map((t) => t.id));
  };

  const doneRatio = (list: PlannerTask[]) =>
    list.length ? Math.round((list.filter((t) => t.status === "done").length / list.length) * 100) : 0;

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCorners}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
    >
      <div className="flex gap-4 overflow-x-auto pb-2">
        <Column
          id={BACKLOG}
          title="📥 백로그"
          subtitle="일정 미배정 태스크"
          tasks={byColumn.get(BACKLOG) ?? []}
          questTitles={questTitles}
          readOnly={readOnly}
          onAddTask={readOnly ? undefined : () => onAddTask(null)}
          onTaskClick={onTaskClick}
          headerExtra={decomposeSlot}
        />
        {board.sprints.map((s: Sprint) => {
          const list = byColumn.get(colId(s.id)) ?? [];
          return (
            <Column
              key={s.id}
              id={colId(s.id)}
              title={s.title}
              subtitle={`${s.startDate.slice(5)} ~ ${s.endDate.slice(5)}${s.goal ? ` · ${s.goal}` : ""}`}
              tasks={list}
              questTitles={questTitles}
              readOnly={readOnly}
              progress={doneRatio(list)}
              onAddTask={readOnly ? undefined : () => onAddTask(s.id)}
              onDeleteSprint={readOnly ? undefined : () => onDeleteSprint(s.id)}
              onTaskClick={onTaskClick}
            />
          );
        })}
        {!readOnly ? (
          <button
            type="button"
            onClick={onAddSprint}
            className="flex h-24 w-56 shrink-0 items-center justify-center gap-1.5 rounded-2xl border-2 border-dashed border-slate-200 text-sm font-semibold text-slate-400 transition hover:border-indigo-300 hover:text-indigo-600 dark:border-slate-700 dark:hover:border-indigo-700"
          >
            <Plus className="h-4 w-4" />
            스프린트 추가
          </button>
        ) : null}
        <div className="hidden">
          <Inbox className="h-4 w-4" />
        </div>
      </div>
      <DragOverlay>
        {activeTask ? (
          <TaskCard
            task={activeTask}
            questTitle={activeTask.questKey ? questTitles.get(activeTask.questKey) : undefined}
          />
        ) : null}
      </DragOverlay>
    </DndContext>
  );
}
