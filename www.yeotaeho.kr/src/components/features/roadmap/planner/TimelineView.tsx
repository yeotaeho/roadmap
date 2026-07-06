"use client";

// 플래너 주간 타임라인(간트) 뷰 — CSS Grid 7열, 태스크 기간 bar·스프린트 음영 밴드

import { CalendarClock, ChevronLeft, ChevronRight } from "lucide-react";
import { useMemo, useState } from "react";
import type { PlannerBoard, PlannerTask } from "@/lib/api/planner";

const DAY_MS = 24 * 60 * 60 * 1000;
const WEEK_LABELS = ["일", "월", "화", "수", "목", "금", "토"];

// 스프린트별 순환 pastel 팔레트 — 라이트 100번대 / 다크 900번대
const BAR_PALETTE = [
  "bg-sky-100 text-sky-900 border-sky-200 dark:bg-sky-900/40 dark:text-sky-200 dark:border-sky-800",
  "bg-emerald-100 text-emerald-900 border-emerald-200 dark:bg-emerald-900/40 dark:text-emerald-200 dark:border-emerald-800",
  "bg-violet-100 text-violet-900 border-violet-200 dark:bg-violet-900/40 dark:text-violet-200 dark:border-violet-800",
  "bg-rose-100 text-rose-900 border-rose-200 dark:bg-rose-900/40 dark:text-rose-200 dark:border-rose-800",
];
const BACKLOG_BAR =
  "bg-slate-100 text-slate-700 border-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700";

function startOfWeek(base: Date): Date {
  const d = new Date(base.getFullYear(), base.getMonth(), base.getDate());
  d.setDate(d.getDate() - d.getDay()); // 일요일 시작
  return d;
}

function parseDate(iso: string): Date {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d);
}

function dayDiff(a: Date, b: Date): number {
  return Math.round((b.getTime() - a.getTime()) / DAY_MS);
}

export function TimelineView({
  board,
  onTaskClick,
}: {
  board: PlannerBoard;
  onTaskClick: (t: PlannerTask) => void;
}) {
  const [weekOffset, setWeekOffset] = useState(0);
  const today = useMemo(() => new Date(), []);
  const weekStart = useMemo(() => {
    const s = startOfWeek(today);
    s.setDate(s.getDate() + weekOffset * 7);
    return s;
  }, [today, weekOffset]);

  const days = useMemo(
    () => Array.from({ length: 7 }, (_, i) => new Date(weekStart.getTime() + i * DAY_MS)),
    [weekStart],
  );
  const weekEnd = days[6];

  const sprintColor = useMemo(() => {
    const m = new Map<number, string>();
    board.sprints.forEach((s, i) => m.set(s.id, BAR_PALETTE[i % BAR_PALETTE.length]));
    return m;
  }, [board.sprints]);

  // 이번 주와 겹치는 기간 태스크만 bar 로
  const bars = useMemo(() => {
    return board.tasks
      .filter((t) => t.startDate && t.dueDate)
      .map((t) => {
        const s = parseDate(t.startDate as string);
        const e = parseDate(t.dueDate as string);
        return { task: t, start: s, end: e };
      })
      .filter(({ start, end }) => start <= weekEnd && end >= weekStart)
      .map(({ task, start, end }) => {
        const colStart = Math.max(0, dayDiff(weekStart, start));
        const colEnd = Math.min(6, dayDiff(weekStart, end));
        return { task, colStart, span: colEnd - colStart + 1, days: dayDiff(start, end) + 1 };
      });
  }, [board.tasks, weekStart, weekEnd]);

  // 이번 주와 겹치는 스프린트 음영 밴드
  const bands = useMemo(() => {
    return board.sprints
      .map((s) => ({ s, start: parseDate(s.startDate), end: parseDate(s.endDate) }))
      .filter(({ start, end }) => start <= weekEnd && end >= weekStart)
      .map(({ s, start, end }) => ({
        sprint: s,
        colStart: Math.max(0, dayDiff(weekStart, start)),
        span: Math.min(6, dayDiff(weekStart, end)) - Math.max(0, dayDiff(weekStart, start)) + 1,
      }));
  }, [board.sprints, weekStart, weekEnd]);

  const unscheduled = board.tasks.filter((t) => !t.startDate || !t.dueDate);
  const isToday = (d: Date) =>
    d.getFullYear() === today.getFullYear() &&
    d.getMonth() === today.getMonth() &&
    d.getDate() === today.getDate();

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_240px]">
      <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-800">
        <div className="flex items-center justify-between gap-2">
          <h3 className="inline-flex items-center gap-2 text-sm font-bold text-slate-900 dark:text-slate-100">
            <CalendarClock className="h-4 w-4 text-indigo-600" />
            {weekStart.getFullYear()}년 {weekStart.getMonth() + 1}월
          </h3>
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => setWeekOffset((x) => x - 1)}
              className="rounded-lg border border-slate-200 p-1.5 text-slate-600 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-900"
              aria-label="이전 주"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <button
              type="button"
              onClick={() => setWeekOffset(0)}
              className="rounded-lg border border-slate-200 px-2.5 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-900"
            >
              오늘
            </button>
            <button
              type="button"
              onClick={() => setWeekOffset((x) => x + 1)}
              className="rounded-lg border border-slate-200 p-1.5 text-slate-600 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-900"
              aria-label="다음 주"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* 요일 헤더 */}
        <div className="mt-4 grid grid-cols-7 gap-1">
          {days.map((d, i) => (
            <div
              key={i}
              className={`rounded-lg py-1.5 text-center text-[11px] font-semibold ${
                isToday(d)
                  ? "bg-indigo-600 text-white"
                  : "text-slate-500 dark:text-slate-400"
              }`}
            >
              {WEEK_LABELS[d.getDay()]} {d.getDate()}
            </div>
          ))}
        </div>

        {/* 스프린트 음영 밴드 */}
        <div className="relative mt-1">
          {bands.map(({ sprint, colStart, span }) => (
            <div key={sprint.id} className="grid grid-cols-7 gap-1">
              <div
                className="mb-1 rounded-md bg-indigo-50/70 px-2 py-0.5 text-[10px] font-semibold text-indigo-500 dark:bg-indigo-900/15 dark:text-indigo-400"
                style={{ gridColumn: `${colStart + 1} / span ${span}` }}
              >
                {sprint.title}
              </div>
            </div>
          ))}

          {/* 태스크 bar */}
          <div className="mt-1 space-y-1.5">
            {bars.length === 0 ? (
              <p className="rounded-xl border border-dashed border-slate-200 p-8 text-center text-xs text-slate-400 dark:border-slate-700">
                이번 주에 걸친 일정이 없습니다. 카드에 시작일·마감일을 넣어보세요.
              </p>
            ) : (
              bars.map(({ task, colStart, span, days: totalDays }) => (
                <div key={task.id} className="grid grid-cols-7 gap-1">
                  <button
                    type="button"
                    onClick={() => onTaskClick(task)}
                    style={{ gridColumn: `${colStart + 1} / span ${span}` }}
                    className={`truncate rounded-lg border px-2.5 py-1.5 text-left text-[11px] font-semibold shadow-sm transition hover:shadow ${
                      task.sprintId != null
                        ? sprintColor.get(task.sprintId) ?? BACKLOG_BAR
                        : BACKLOG_BAR
                    } ${task.status === "done" ? "line-through opacity-60" : ""}`}
                  >
                    {task.title}
                    <span className="ml-1.5 font-normal opacity-70">{totalDays}일</span>
                  </button>
                </div>
              ))
            )}
          </div>
        </div>
      </section>

      {/* 일정 미정 패널 */}
      <section className="rounded-2xl border border-slate-200 bg-[#F8FAFC] p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900">
        <p className="text-xs font-bold text-slate-900 dark:text-slate-100">
          일정 미정 {unscheduled.length}건
        </p>
        <p className="mt-0.5 text-[11px] text-slate-500 dark:text-slate-500">
          클릭해 시작일·마감일을 부여하세요.
        </p>
        <div className="mt-3 space-y-2">
          {unscheduled.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => onTaskClick(t)}
              className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-left text-xs font-medium text-slate-800 shadow-sm transition hover:border-indigo-300 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
            >
              {t.title}
              {t.estimatedDays ? (
                <span className="ml-1 text-[10px] text-slate-400">약 {t.estimatedDays}일</span>
              ) : null}
            </button>
          ))}
          {unscheduled.length === 0 ? (
            <p className="text-center text-[11px] text-slate-400">모든 태스크에 일정이 있습니다.</p>
          ) : null}
        </div>
      </section>
    </div>
  );
}
