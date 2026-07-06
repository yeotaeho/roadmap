"use client";

// 플래너 월간 타임라인 — 달력 격자에 다일 태스크를 걸친 만큼 연속 bar 로 표시(주 경계에서만 이어짐)

import { CalendarClock, ChevronLeft, ChevronRight } from "lucide-react";
import { useMemo, useState } from "react";
import type { PlannerBoard, PlannerTask } from "@/lib/api/planner";

const DAY_MS = 24 * 60 * 60 * 1000;
const WEEK_LABELS = ["일", "월", "화", "수", "목", "금", "토"];

// 스프린트별 순환 pastel 팔레트 — 라이트 100번대 / 다크 900번대
const BAR_PALETTE = [
  "bg-sky-100 text-sky-900 dark:bg-sky-900/50 dark:text-sky-200",
  "bg-emerald-100 text-emerald-900 dark:bg-emerald-900/50 dark:text-emerald-200",
  "bg-violet-100 text-violet-900 dark:bg-violet-900/50 dark:text-violet-200",
  "bg-rose-100 text-rose-900 dark:bg-rose-900/50 dark:text-rose-200",
];
const BACKLOG_BAR = "bg-slate-100 text-slate-700 dark:bg-slate-700 dark:text-slate-200";

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

function dayDiff(a: Date, b: Date): number {
  return Math.round((b.getTime() - a.getTime()) / DAY_MS);
}

type Segment = {
  task: PlannerTask;
  startIdx: number; // 0~6 (주 내 시작 컬럼)
  endIdx: number; // 0~6 (주 내 끝 컬럼)
  realStart: boolean; // 태스크 실제 시작이 이 주 안
  realEnd: boolean; // 태스크 실제 끝이 이 주 안
  totalDays: number;
};

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

  // 6주 × 7일 셀을 주 단위로 묶는다(성장 아카이브와 동일 규약)
  const weeks = useMemo(() => {
    const cells: { date: Date; inMonth: boolean }[] = [];
    for (let i = firstDow - 1; i >= 0; i--) {
      cells.push({ date: new Date(year, month, -i), inMonth: false });
    }
    for (let d = 1; d <= daysInMonth; d++) {
      cells.push({ date: new Date(year, month, d), inMonth: true });
    }
    while (cells.length % 7 !== 0 || cells.length < 42) {
      const last = cells[cells.length - 1]!.date;
      const next = new Date(last);
      next.setDate(next.getDate() + 1);
      cells.push({ date: next, inMonth: false });
    }
    const grouped: { date: Date; inMonth: boolean }[][] = [];
    for (let i = 0; i < cells.length; i += 7) grouped.push(cells.slice(i, i + 7));
    return grouped;
  }, [year, month, firstDow, daysInMonth]);

  const sprintColor = useMemo(() => {
    const m = new Map<number, string>();
    board.sprints.forEach((s, i) => m.set(s.id, BAR_PALETTE[i % BAR_PALETTE.length]!));
    return m;
  }, [board.sprints]);

  const barColor = (t: PlannerTask) =>
    t.sprintId != null ? sprintColor.get(t.sprintId) ?? BACKLOG_BAR : BACKLOG_BAR;

  // 기간 태스크(시작~마감) 목록
  const dated = useMemo(
    () =>
      board.tasks
        .filter((t) => t.startDate && t.dueDate)
        .map((t) => ({ task: t, start: parseDate(t.startDate!), end: parseDate(t.dueDate!) }))
        .filter(({ start, end }) => end >= start),
    [board.tasks],
  );

  // 한 주에 걸치는 태스크를 세그먼트로 자르고 겹치지 않게 레인 배치
  const lanesOfWeek = (week: { date: Date }[]): Segment[][] => {
    const ws = week[0]!.date;
    const we = week[6]!.date;
    const segs: Segment[] = [];
    for (const { task, start, end } of dated) {
      if (start > we || end < ws) continue;
      const startIdx = Math.max(0, dayDiff(ws, start));
      const endIdx = Math.min(6, dayDiff(ws, end));
      if (endIdx < startIdx) continue;
      segs.push({
        task,
        startIdx,
        endIdx,
        realStart: start >= ws,
        realEnd: end <= we,
        totalDays: dayDiff(start, end) + 1,
      });
    }
    segs.sort(
      (a, b) => a.startIdx - b.startIdx || b.endIdx - b.startIdx - (a.endIdx - a.startIdx),
    );
    const lanes: Segment[][] = [];
    for (const seg of segs) {
      const lane = lanes.find((L) =>
        L.every((x) => seg.startIdx > x.endIdx || seg.endIdx < x.startIdx),
      );
      if (lane) lane.push(seg);
      else lanes.push([seg]);
    }
    return lanes;
  };

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

        {/* 주 단위 격자 — 배경 셀 + 연속 bar 레인 */}
        <div className="mt-1 space-y-1">
          {weeks.map((week, wi) => {
            const lanes = lanesOfWeek(week);
            return (
              <div key={wi} className="relative" style={{ minHeight: 96 }}>
                {/* 배경 날짜 셀 */}
                <div className="absolute inset-0 grid grid-cols-7 gap-1">
                  {week.map(({ date, inMonth }, i) => (
                    <div
                      key={i}
                      className={`rounded-xl border ${
                        !inMonth
                          ? "border-transparent bg-slate-50/40 dark:bg-slate-900/40"
                          : isToday(date)
                            ? "border-indigo-300 bg-indigo-50/40 dark:border-indigo-800 dark:bg-indigo-900/15"
                            : "border-slate-100 bg-white dark:border-slate-700 dark:bg-slate-900/60"
                      }`}
                    />
                  ))}
                </div>

                {/* 전경 — 날짜 숫자 + 연속 bar 레인 */}
                <div className="relative">
                  <div className="grid grid-cols-7 gap-1">
                    {week.map(({ date, inMonth }, i) => (
                      <div
                        key={i}
                        className={`px-1.5 pt-1.5 text-[11px] font-semibold ${
                          !inMonth
                            ? "text-slate-300 dark:text-slate-600"
                            : isToday(date)
                              ? "text-indigo-700 dark:text-indigo-300"
                              : "text-slate-600 dark:text-slate-400"
                        }`}
                      >
                        {date.getDate()}
                      </div>
                    ))}
                  </div>

                  <div className="mt-0.5 space-y-0.5 pb-1.5">
                    {lanes.map((lane, li) => (
                      <div key={li} className="grid grid-cols-7 gap-1">
                        {lane.map((seg) => (
                          <button
                            key={seg.task.id}
                            type="button"
                            onClick={() => onTaskClick(seg.task)}
                            title={`${seg.task.title} · ${seg.totalDays}일`}
                            style={{ gridColumn: `${seg.startIdx + 1} / span ${seg.endIdx - seg.startIdx + 1}` }}
                            className={`mx-0.5 truncate px-1.5 py-0.5 text-left text-[10px] font-semibold shadow-sm transition hover:opacity-80 ${barColor(
                              seg.task,
                            )} ${seg.realStart ? "rounded-l-md" : "rounded-l-none"} ${
                              seg.realEnd ? "rounded-r-md" : "rounded-r-none"
                            } ${seg.task.status === "done" ? "line-through opacity-60" : ""}`}
                          >
                            {seg.task.title}
                          </button>
                        ))}
                      </div>
                    ))}
                  </div>
                </div>
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
