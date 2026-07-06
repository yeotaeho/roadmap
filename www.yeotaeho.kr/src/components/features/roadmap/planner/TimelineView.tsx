"use client";

// 플래너 주간 타임라인 — 가로 간트(요일 컬럼 위 기간 bar·세로 그리드선·오늘 강조)

import {
  CalendarClock,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Circle,
  CircleDot,
  type LucideIcon,
} from "lucide-react";
import { useMemo, useState } from "react";
import type { PlannerBoard, PlannerTask, TaskStatus } from "@/lib/api/planner";

const DAY_MS = 24 * 60 * 60 * 1000;
const WEEK_LABELS = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"];

// 스프린트별 순환 pastel — bar 배경·텍스트·아이콘 칩
type Palette = { bar: string; text: string; chip: string };
const BAR_PALETTE: Palette[] = [
  {
    bar: "bg-sky-100 dark:bg-sky-900/40",
    text: "text-sky-900 dark:text-sky-100",
    chip: "bg-white/70 text-sky-600 dark:bg-sky-950/60 dark:text-sky-300",
  },
  {
    bar: "bg-emerald-100 dark:bg-emerald-900/40",
    text: "text-emerald-900 dark:text-emerald-100",
    chip: "bg-white/70 text-emerald-600 dark:bg-emerald-950/60 dark:text-emerald-300",
  },
  {
    bar: "bg-violet-100 dark:bg-violet-900/40",
    text: "text-violet-900 dark:text-violet-100",
    chip: "bg-white/70 text-violet-600 dark:bg-violet-950/60 dark:text-violet-300",
  },
  {
    bar: "bg-rose-100 dark:bg-rose-900/40",
    text: "text-rose-900 dark:text-rose-100",
    chip: "bg-white/70 text-rose-600 dark:bg-rose-950/60 dark:text-rose-300",
  },
];
const BACKLOG_PALETTE: Palette = {
  bar: "bg-slate-100 dark:bg-slate-800",
  text: "text-slate-700 dark:text-slate-200",
  chip: "bg-white/70 text-slate-500 dark:bg-slate-900/60 dark:text-slate-300",
};

const STATUS_ICON: Record<TaskStatus, LucideIcon> = {
  todo: Circle,
  doing: CircleDot,
  done: CheckCircle2,
};

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
  const weekEnd = days[6]!;

  const sprintColor = useMemo(() => {
    const m = new Map<number, Palette>();
    board.sprints.forEach((s, i) => m.set(s.id, BAR_PALETTE[i % BAR_PALETTE.length]!));
    return m;
  }, [board.sprints]);

  const paletteOf = (t: PlannerTask): Palette =>
    t.sprintId != null ? sprintColor.get(t.sprintId) ?? BACKLOG_PALETTE : BACKLOG_PALETTE;

  // 이번 주와 겹치는 기간 태스크만 bar 로 (시작일 오름차순)
  const bars = useMemo(() => {
    return board.tasks
      .filter((t) => t.startDate && t.dueDate)
      .map((t) => ({ task: t, start: parseDate(t.startDate!), end: parseDate(t.dueDate!) }))
      .filter(({ start, end }) => start <= weekEnd && end >= weekStart)
      .sort((a, b) => a.start.getTime() - b.start.getTime())
      .map(({ task, start, end }) => {
        const colStart = Math.max(0, dayDiff(weekStart, start));
        const colEnd = Math.min(6, dayDiff(weekStart, end));
        return { task, colStart, span: colEnd - colStart + 1, totalDays: dayDiff(start, end) + 1 };
      });
  }, [board.tasks, weekStart, weekEnd]);

  const unscheduled = board.tasks.filter((t) => !t.startDate || !t.dueDate);
  const isToday = (d: Date) => dayDiff(today, d) === 0 && d.getMonth() === today.getMonth();

  return (
    <div className="space-y-4">
      <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-800">
        {/* 상단 바 — 월 라벨 + 주 이동 */}
        <div className="flex items-center justify-between gap-2 border-b border-slate-100 px-4 py-3 dark:border-slate-700">
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

        <div className="overflow-x-auto">
          <div className="min-w-[640px]">
            {/* 요일 헤더 */}
            <div className="grid grid-cols-7 border-b border-slate-100 dark:border-slate-700">
              {days.map((d, i) => (
                <div
                  key={i}
                  className={`border-r border-slate-100 px-2 py-2.5 text-center last:border-r-0 dark:border-slate-700 ${
                    isToday(d) ? "bg-indigo-50/60 dark:bg-indigo-900/15" : ""
                  }`}
                >
                  <span
                    className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold ${
                      isToday(d)
                        ? "bg-indigo-600 text-white"
                        : "text-slate-400 dark:text-slate-500"
                    }`}
                  >
                    {WEEK_LABELS[d.getDay()]} {d.getDate()}
                  </span>
                </div>
              ))}
            </div>

            {/* 간트 본문 — 배경 그리드선 + 기간 bar */}
            <div className="relative">
              {/* 세로 그리드선 + 오늘 컬럼 음영 (전체 높이) */}
              <div className="pointer-events-none absolute inset-0 grid grid-cols-7">
                {days.map((d, i) => (
                  <div
                    key={i}
                    className={`border-r border-slate-100 last:border-r-0 dark:border-slate-700/70 ${
                      isToday(d) ? "bg-indigo-50/40 dark:bg-indigo-900/10" : ""
                    }`}
                  />
                ))}
              </div>

              {/* bar 행 */}
              <div className="relative space-y-1.5 py-3">
                {bars.length === 0 ? (
                  <p className="px-4 py-10 text-center text-xs text-slate-400">
                    이번 주에 걸친 일정이 없습니다. 카드에 시작일·마감일을 넣어보세요.
                  </p>
                ) : (
                  bars.map(({ task, colStart, span, totalDays }) => {
                    const p = paletteOf(task);
                    const Icon = STATUS_ICON[task.status];
                    return (
                      <div key={task.id} className="grid grid-cols-7 px-1.5">
                        <button
                          type="button"
                          onClick={() => onTaskClick(task)}
                          style={{ gridColumn: `${colStart + 1} / span ${span}` }}
                          title={task.title}
                          className={`flex items-center gap-1.5 rounded-lg px-2 py-1.5 text-left shadow-sm transition hover:brightness-95 dark:hover:brightness-110 ${
                            p.bar
                          } ${task.status === "done" ? "opacity-70" : ""}`}
                        >
                          <span className={`grid h-4 w-4 shrink-0 place-items-center rounded ${p.chip}`}>
                            <Icon className="h-2.5 w-2.5" />
                          </span>
                          <span
                            className={`truncate text-[11px] font-semibold ${p.text} ${
                              task.status === "done" ? "line-through" : ""
                            }`}
                          >
                            {task.title}
                          </span>
                          <span className={`shrink-0 text-[10px] font-normal opacity-60 ${p.text}`}>
                            · {totalDays}일
                          </span>
                        </button>
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 일정 미정 — 하단 칩 스트립 */}
      {unscheduled.length > 0 ? (
        <section className="rounded-2xl border border-slate-200 bg-[#F8FAFC] p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900">
          <p className="text-xs font-bold text-slate-900 dark:text-slate-100">
            일정 미정 {unscheduled.length}건
          </p>
          <p className="mt-0.5 text-[11px] text-slate-500 dark:text-slate-500">
            클릭해 시작일·마감일을 부여하면 타임라인에 올라갑니다.
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            {unscheduled.map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => onTaskClick(t)}
                className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-left text-xs font-medium text-slate-800 shadow-sm transition hover:border-indigo-300 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200"
              >
                {t.title}
                {t.estimatedDays ? (
                  <span className="ml-1 text-[10px] text-slate-400">약 {t.estimatedDays}일</span>
                ) : null}
              </button>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}
