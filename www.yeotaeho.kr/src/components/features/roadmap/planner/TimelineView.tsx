"use client";

// 플래너 월간 타임라인 — 달력 격자(주 단위 행)에 태스크를 날짜 칩으로 배치

import { CalendarClock, ChevronLeft, ChevronRight } from "lucide-react";
import { useMemo, useState } from "react";
import type { PlannerBoard, PlannerTask } from "@/lib/api/planner";

const WEEK_LABELS = ["일", "월", "화", "수", "목", "금", "토"];
const MAX_CHIPS = 3;

// 스프린트별 순환 pastel 팔레트 — 라이트 100번대 / 다크 900번대
const CHIP_PALETTE = [
  "bg-sky-100 text-sky-900 dark:bg-sky-900/40 dark:text-sky-200",
  "bg-emerald-100 text-emerald-900 dark:bg-emerald-900/40 dark:text-emerald-200",
  "bg-violet-100 text-violet-900 dark:bg-violet-900/40 dark:text-violet-200",
  "bg-rose-100 text-rose-900 dark:bg-rose-900/40 dark:text-rose-200",
];
const BACKLOG_CHIP = "bg-slate-100 text-slate-700 dark:bg-slate-700 dark:text-slate-300";

function pad2(n: number): string {
  return String(n).padStart(2, "0");
}

function toKey(d: Date): string {
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
}

function parseDate(iso: string): Date {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d);
}

export function TimelineView({
  board,
  onTaskClick,
}: {
  board: PlannerBoard;
  onTaskClick: (t: PlannerTask) => void;
}) {
  const [monthOffset, setMonthOffset] = useState(0);
  const today = useMemo(() => new Date(), []);
  const viewMonth = useMemo(
    () => new Date(today.getFullYear(), today.getMonth() + monthOffset, 1),
    [today, monthOffset],
  );

  const year = viewMonth.getFullYear();
  const month = viewMonth.getMonth();
  const firstDow = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();

  // 달력 셀 6주(42칸) — 앞뒤 달 채움(성장 아카이브와 동일 규약)
  const cells = useMemo(() => {
    const arr: { date: Date; inMonth: boolean }[] = [];
    for (let i = firstDow - 1; i >= 0; i--) {
      arr.push({ date: new Date(year, month, -i), inMonth: false });
    }
    for (let d = 1; d <= daysInMonth; d++) {
      arr.push({ date: new Date(year, month, d), inMonth: true });
    }
    while (arr.length % 7 !== 0 || arr.length < 42) {
      const last = arr[arr.length - 1]!.date;
      const next = new Date(last);
      next.setDate(next.getDate() + 1);
      arr.push({ date: next, inMonth: false });
    }
    return arr;
  }, [year, month, firstDow, daysInMonth]);

  const sprintColor = useMemo(() => {
    const m = new Map<number, string>();
    board.sprints.forEach((s, i) => m.set(s.id, CHIP_PALETTE[i % CHIP_PALETTE.length]!));
    return m;
  }, [board.sprints]);

  const chipColor = (t: PlannerTask) =>
    t.sprintId != null ? sprintColor.get(t.sprintId) ?? BACKLOG_CHIP : BACKLOG_CHIP;

  // 날짜별 태스크 배치 — [startDate, dueDate] 범위의 각 날에 칩. 역전 범위는 자연 스킵.
  const taskByDay = useMemo(() => {
    const m = new Map<string, PlannerTask[]>();
    for (const t of board.tasks) {
      if (!t.startDate || !t.dueDate) continue;
      let cur = parseDate(t.startDate);
      const end = parseDate(t.dueDate);
      let guard = 0;
      while (cur <= end && guard < 366) {
        const key = toKey(cur);
        if (!m.has(key)) m.set(key, []);
        m.get(key)!.push(t);
        cur = new Date(cur.getFullYear(), cur.getMonth(), cur.getDate() + 1);
        guard += 1;
      }
    }
    return m;
  }, [board.tasks]);

  const unscheduled = board.tasks.filter((t) => !t.startDate || !t.dueDate);
  const isToday = (d: Date) => toKey(d) === toKey(today);

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_240px]">
      <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-800">
        <div className="flex items-center justify-between gap-2">
          <h3 className="inline-flex items-center gap-2 text-sm font-bold text-slate-900 dark:text-slate-100">
            <CalendarClock className="h-4 w-4 text-indigo-600" />
            {year}년 {month + 1}월
          </h3>
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => setMonthOffset((x) => x - 1)}
              className="rounded-lg border border-slate-200 p-1.5 text-slate-600 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-900"
              aria-label="이전 달"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <button
              type="button"
              onClick={() => setMonthOffset(0)}
              className="rounded-lg border border-slate-200 px-2.5 py-1 text-xs font-semibold text-slate-700 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-900"
            >
              오늘
            </button>
            <button
              type="button"
              onClick={() => setMonthOffset((x) => x + 1)}
              className="rounded-lg border border-slate-200 p-1.5 text-slate-600 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-900"
              aria-label="다음 달"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* 요일 헤더 */}
        <div className="mt-4 grid grid-cols-7 gap-1 text-center text-[11px] font-semibold text-slate-500 dark:text-slate-500">
          {WEEK_LABELS.map((w) => (
            <div key={w} className="py-1">
              {w}
            </div>
          ))}
        </div>

        {/* 날짜 격자 */}
        <div className="mt-1 grid grid-cols-7 gap-1">
          {cells.map(({ date, inMonth }) => {
            const key = toKey(date);
            const dayTasks = taskByDay.get(key) ?? [];
            return (
              <div
                key={key}
                className={`flex min-h-[92px] flex-col gap-1 rounded-xl border p-1.5 ${
                  !inMonth
                    ? "border-transparent bg-slate-50/40 dark:bg-slate-900/40"
                    : isToday(date)
                      ? "border-indigo-300 bg-indigo-50/40 dark:border-indigo-800 dark:bg-indigo-900/15"
                      : "border-slate-100 bg-white dark:border-slate-700 dark:bg-slate-900/60"
                }`}
              >
                <span
                  className={`text-[11px] font-semibold ${
                    !inMonth
                      ? "text-slate-300 dark:text-slate-600"
                      : isToday(date)
                        ? "text-indigo-700 dark:text-indigo-300"
                        : "text-slate-600 dark:text-slate-400"
                  }`}
                >
                  {date.getDate()}
                </span>
                {dayTasks.slice(0, MAX_CHIPS).map((t) => (
                  <button
                    key={t.id}
                    type="button"
                    onClick={() => onTaskClick(t)}
                    title={t.title}
                    className={`truncate rounded-md px-1.5 py-0.5 text-left text-[10px] font-semibold transition hover:opacity-80 ${chipColor(
                      t,
                    )} ${t.status === "done" ? "line-through opacity-60" : ""}`}
                  >
                    {t.title}
                  </button>
                ))}
                {dayTasks.length > MAX_CHIPS ? (
                  <span className="px-1 text-[9px] font-medium text-slate-400">
                    +{dayTasks.length - MAX_CHIPS}건
                  </span>
                ) : null}
              </div>
            );
          })}
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
