"use client";

// 플래너 태스크 카드 — 보드·백로그 공용 (퀘스트 칩·AI 배지·기간)

import { Bot, CalendarRange } from "lucide-react";
import type { PlannerTask } from "@/lib/api/planner";

const STATUS_STYLE: Record<string, string> = {
  todo: "border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-800",
  doing:
    "border-indigo-300 bg-indigo-50/60 ring-1 ring-indigo-200/60 dark:border-indigo-700 dark:bg-indigo-900/20 dark:ring-indigo-900/40",
  done: "border-emerald-200 bg-emerald-50/40 opacity-80 dark:border-emerald-900/40 dark:bg-emerald-900/10",
};

export function TaskCard({
  task,
  questTitle,
  onClick,
}: {
  task: PlannerTask;
  questTitle?: string;
  onClick?: () => void;
}) {
  return (
    <div
      onClick={onClick}
      className={`cursor-grab rounded-xl border p-3 shadow-sm transition hover:shadow-md active:cursor-grabbing ${
        STATUS_STYLE[task.status] ?? STATUS_STYLE.todo
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <p
          className={`text-xs font-semibold text-slate-900 dark:text-slate-100 ${
            task.status === "done" ? "line-through" : ""
          }`}
        >
          {task.title}
        </p>
        {task.source === "ai" ? (
          <span className="inline-flex shrink-0 items-center gap-0.5 rounded-full bg-violet-100 px-1.5 py-0.5 text-[9px] font-bold text-violet-700 dark:bg-violet-900/35 dark:text-violet-300">
            <Bot className="h-2.5 w-2.5" />
            AI
          </span>
        ) : null}
      </div>
      {task.description ? (
        <p className="mt-1 line-clamp-2 text-[11px] text-slate-600 dark:text-slate-400">
          {task.description}
        </p>
      ) : null}
      <div className="mt-2 flex flex-wrap items-center gap-1.5">
        {questTitle ? (
          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-600 dark:bg-slate-700 dark:text-slate-300">
            🗺 {questTitle}
          </span>
        ) : null}
        {task.dueDate ? (
          <span className="inline-flex items-center gap-0.5 rounded-full bg-sky-50 px-2 py-0.5 text-[10px] font-medium text-sky-700 dark:bg-sky-900/25 dark:text-sky-300">
            <CalendarRange className="h-2.5 w-2.5" />
            ~{task.dueDate.slice(5).replace("-", "/")}
          </span>
        ) : task.estimatedDays ? (
          <span className="rounded-full bg-slate-50 px-2 py-0.5 text-[10px] text-slate-500 dark:bg-slate-900 dark:text-slate-400">
            약 {task.estimatedDays}일
          </span>
        ) : null}
      </div>
    </div>
  );
}
