"use client";

// 플래너 월간 타임라인 — 달력 격자(연속 bar) + 날짜 클릭 시 Daily Log(퀘스트 체크리스트·자유 기록) 흡수(구 성장 아카이브)

import { motion } from "framer-motion";
import { CalendarClock, ChevronLeft, ChevronRight, Save } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { ARCHIVE_ACTIVITY_SEED, flattenQuestTitles, QUEST_TREE } from "@/data/roadmapQuestMap";
import { useArchive, useJourney, useUpsertArchiveDay } from "@/hooks/useRoadmap";
import type { PlannerBoard, PlannerTask } from "@/lib/api/planner";

const DAY_MS = 24 * 60 * 60 * 1000;
const WEEK_LABELS = ["일", "월", "화", "수", "목", "금", "토"];

type DayLog = {
  completedQuestIds: string[];
  note: string;
};

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

function parseKey(key: string): Date {
  const [y, m, d] = key.split("-").map(Number);
  return new Date(y, m - 1, d);
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
  enabled,
  onTaskClick,
}: {
  board: PlannerBoard;
  enabled: boolean;
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
  const monthKey = `${year}-${pad2(month + 1)}`;

  // ── Daily Log (구 성장 아카이브 흡수) — 퀘스트 체크리스트·자유 기록·저장 ──
  const { data: journey } = useJourney(enabled);
  const allQuests = useMemo(
    () => flattenQuestTitles(journey?.questTree ?? QUEST_TREE).filter((q) => q.id !== "root"),
    [journey],
  );
  const [logs, setLogs] = useState<Record<string, DayLog>>(() => ({ ...ARCHIVE_ACTIVITY_SEED }));
  const [selectedKey, setSelectedKey] = useState<string>(() => toKey(today));

  // 보고 있는 달의 로그를 백엔드에서 받아 로컬 state 에 병합(서버가 진실원).
  const { data: monthLogs } = useArchive(monthKey, enabled);
  useEffect(() => {
    if (monthLogs) setLogs((prev) => ({ ...prev, ...monthLogs }));
  }, [monthLogs]);

  const upsertDay = useUpsertArchiveDay();
  const selectedLog = logs[selectedKey] ?? { completedQuestIds: [], note: "" };

  const toggleQuest = (id: string) => {
    setLogs((prev) => {
      const cur = prev[selectedKey] ?? { completedQuestIds: [], note: "" };
      const set = new Set(cur.completedQuestIds);
      if (set.has(id)) set.delete(id);
      else set.add(id);
      return { ...prev, [selectedKey]: { ...cur, completedQuestIds: Array.from(set) } };
    });
  };

  const setNote = (note: string) => {
    setLogs((prev) => ({
      ...prev,
      [selectedKey]: { ...(prev[selectedKey] ?? { completedQuestIds: [], note: "" }), note },
    }));
  };

  const saveLog = () => {
    const cur = logs[selectedKey] ?? { completedQuestIds: [], note: "" };
    setLogs((prev) => ({ ...prev, [selectedKey]: cur }));
    // 로그인 사용자만 서버 영속화. 비로그인은 로컬 보존(추후 로그인 유도).
    if (enabled) upsertDay.mutate({ date: selectedKey, payload: cur });
  };

  const hasActivity = (key: string) => {
    const e = logs[key];
    return Boolean(e && (e.note.trim().length > 0 || e.completedQuestIds.length > 0));
  };

  // ── 달력 격자(6주) ──
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
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(280px,380px)]">
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
        <p className="mt-2 text-[11px] text-slate-500 dark:text-slate-500">
          날짜를 클릭하면 그날의 Daily Log 를 오른쪽에서 기록합니다.
        </p>

        {/* 요일 헤더 */}
        <div className="mt-3 grid grid-cols-7 gap-1 text-center text-[11px] font-semibold text-slate-500 dark:text-slate-500">
          {WEEK_LABELS.map((w) => (
            <div key={w} className="py-1">
              {w}
            </div>
          ))}
        </div>

        {/* 주 단위 격자 — 배경 셀(날짜 선택) + 연속 bar 레인 */}
        <div className="mt-1 space-y-1">
          {weeks.map((week, wi) => {
            const lanes = lanesOfWeek(week);
            return (
              <div key={wi} className="relative" style={{ minHeight: 96 }}>
                {/* 배경 날짜 셀 — 오늘/선택 강조, 빈 영역 클릭도 날짜 선택 */}
                <div className="absolute inset-0 grid grid-cols-7 gap-1">
                  {week.map(({ date, inMonth }, i) => {
                    const key = toKey(date);
                    const selected = key === selectedKey;
                    return (
                      <button
                        key={i}
                        type="button"
                        onClick={() => inMonth && setSelectedKey(key)}
                        disabled={!inMonth}
                        className={`rounded-xl border text-left ${
                          !inMonth
                            ? "cursor-default border-transparent bg-slate-50/40 dark:bg-slate-900/40"
                            : selected
                              ? "border-indigo-300 bg-indigo-50/50 dark:border-indigo-700 dark:bg-indigo-900/20"
                              : isToday(date)
                                ? "border-emerald-200 bg-emerald-50/30 dark:border-emerald-900/40 dark:bg-emerald-900/10"
                                : "border-slate-100 bg-white hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900/60 dark:hover:bg-slate-900"
                        }`}
                      />
                    );
                  })}
                </div>

                {/* 전경 — 날짜 숫자(클릭 시 선택) + 연속 bar 레인 */}
                <div className="relative">
                  <div className="grid grid-cols-7 gap-1">
                    {week.map(({ date, inMonth }, i) => {
                      const key = toKey(date);
                      const selected = key === selectedKey;
                      return (
                        <button
                          key={i}
                          type="button"
                          onClick={() => setSelectedKey(key)}
                          className="flex items-center gap-1 px-1.5 pt-1.5 text-left"
                        >
                          <span
                            className={`grid h-5 w-5 shrink-0 place-items-center rounded-full text-[11px] font-semibold ${
                              !inMonth
                                ? "text-slate-300 dark:text-slate-600"
                                : selected
                                  ? "bg-indigo-600 text-white"
                                  : isToday(date)
                                    ? "text-emerald-700 dark:text-emerald-300"
                                    : "text-slate-600 dark:text-slate-400"
                            }`}
                          >
                            {date.getDate()}
                          </span>
                          {inMonth && hasActivity(key) ? (
                            <span
                              className={`h-1.5 w-1.5 rounded-full ${
                                selected ? "bg-indigo-500" : "bg-emerald-500"
                              }`}
                            />
                          ) : null}
                        </button>
                      );
                    })}
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
                            style={{
                              gridColumn: `${seg.startIdx + 1} / span ${seg.endIdx - seg.startIdx + 1}`,
                            }}
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

      {/* 우측 — Daily Log(구 성장 아카이브) + 일정 미정 */}
      <div className="flex flex-col gap-4">
        <section className="flex flex-col rounded-2xl border border-slate-200 bg-[#F8FAFC] p-5 shadow-sm dark:border-slate-700 dark:bg-slate-900">
          <p className="text-xs font-semibold text-slate-500 dark:text-slate-500">Daily Log</p>
          <h3 className="mt-1 text-base font-bold text-slate-900 dark:text-slate-100">
            {parseKey(selectedKey).toLocaleDateString("ko-KR", {
              year: "numeric",
              month: "long",
              day: "numeric",
              weekday: "short",
            })}
          </h3>

          <div className="mt-4">
            <p className="text-xs font-semibold text-slate-600 dark:text-slate-400">
              이날 달성한 퀘스트
            </p>
            <div className="mt-2 max-h-40 space-y-2 overflow-y-auto rounded-xl border border-slate-200 bg-white p-2 dark:border-slate-700 dark:bg-slate-800">
              {allQuests.map((q) => (
                <label
                  key={q.id}
                  className="flex cursor-pointer items-start gap-2 rounded-lg px-2 py-1.5 text-xs hover:bg-slate-50 dark:hover:bg-slate-900"
                >
                  <input
                    type="checkbox"
                    checked={selectedLog.completedQuestIds.includes(q.id)}
                    onChange={() => toggleQuest(q.id)}
                    className="mt-0.5 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                  />
                  <span className="text-slate-800 dark:text-slate-200">{q.title}</span>
                </label>
              ))}
            </div>
          </div>

          <div className="mt-4">
            <label
              htmlFor="timeline-daily-log"
              className="text-xs font-semibold text-slate-600 dark:text-slate-400"
            >
              배운 것 · 해결한 것 (마크다운 스타일 자유 기록)
            </label>
            <textarea
              id="timeline-daily-log"
              value={selectedLog.note}
              onChange={(e) => setNote(e.target.value)}
              rows={6}
              className="mt-2 w-full resize-y rounded-2xl border border-slate-200 bg-white p-3 text-sm text-slate-900 shadow-sm placeholder:text-slate-400 focus:border-indigo-300 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100 dark:placeholder:text-slate-500"
              placeholder="예: 오늘은 스키마에서 `scope3` 경계를 어떻게 끊을지 고민했다…"
            />
          </div>

          <motion.button
            type="button"
            whileTap={{ scale: 0.98 }}
            onClick={saveLog}
            disabled={upsertDay.isPending}
            className="mt-4 inline-flex items-center justify-center gap-2 rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-indigo-700 disabled:opacity-60"
          >
            <Save className="h-4 w-4" />
            {upsertDay.isPending ? "저장 중…" : enabled ? "저장" : "저장 (로컬)"}
          </motion.button>
        </section>

        {/* 일정 미정 패널 */}
        <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-800">
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
                className="w-full rounded-xl border border-slate-200 bg-[#F8FAFC] px-3 py-2 text-left text-xs font-medium text-slate-800 shadow-sm transition hover:border-indigo-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
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
    </div>
  );
}
