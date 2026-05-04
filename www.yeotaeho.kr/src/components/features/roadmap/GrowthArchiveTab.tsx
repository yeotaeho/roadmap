"use client";

import { motion } from "framer-motion";
import { CalendarDays, ChevronLeft, ChevronRight, Save } from "lucide-react";
import { useCallback, useMemo, useState } from "react";
import {
  ARCHIVE_ACTIVITY_SEED,
  flattenQuestTitles,
  QUEST_TREE,
} from "@/data/roadmapQuestMap";

type DayLog = {
  completedQuestIds: string[];
  note: string;
};

function pad2(n: number) {
  return String(n).padStart(2, "0");
}

function toKey(d: Date) {
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
}

function parseKey(key: string): Date {
  const [y, m, day] = key.split("-").map(Number);
  return new Date(y, m - 1, day);
}

const WEEK_LABELS = ["일", "월", "화", "수", "목", "금", "토"];

export function GrowthArchiveTab() {
  const allQuests = useMemo(() => flattenQuestTitles(QUEST_TREE).filter((q) => q.id !== "root"), []);

  const [monthOffset, setMonthOffset] = useState(0);
  const today = useMemo(() => new Date(), []);
  const viewMonth = useMemo(() => {
    return new Date(today.getFullYear(), today.getMonth() + monthOffset, 1);
  }, [today, monthOffset]);

  const [logs, setLogs] = useState<Record<string, DayLog>>(() => ({ ...ARCHIVE_ACTIVITY_SEED }));
  const [selectedKey, setSelectedKey] = useState<string>(() => toKey(today));

  const year = viewMonth.getFullYear();
  const month = viewMonth.getMonth();
  const firstDow = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();

  const calendarCells = useMemo(() => {
    const cells: { date: Date; inMonth: boolean }[] = [];
    const prevDays = firstDow;
    for (let i = prevDays - 1; i >= 0; i--) {
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
    return cells;
  }, [year, month, firstDow, daysInMonth]);

  const selectedLog = logs[selectedKey] ?? { completedQuestIds: [], note: "" };
  const questTitleById = useMemo(() => {
    const m = new Map<string, string>();
    for (const q of allQuests) m.set(q.id, q.title);
    return m;
  }, [allQuests]);

  const toggleQuest = (id: string) => {
    setLogs((prev) => {
      const cur = prev[selectedKey] ?? { completedQuestIds: [], note: "" };
      const set = new Set(cur.completedQuestIds);
      if (set.has(id)) set.delete(id);
      else set.add(id);
      return {
        ...prev,
        [selectedKey]: { ...cur, completedQuestIds: Array.from(set) },
      };
    });
  };

  const setNote = (note: string) => {
    setLogs((prev) => ({
      ...prev,
      [selectedKey]: {
        ...(prev[selectedKey] ?? { completedQuestIds: [], note: "" }),
        note,
      },
    }));
  };

  const save = useCallback(() => {
    // 로컬 목업: 추후 API 연동
    setLogs((prev) => ({ ...prev }));
  }, []);

  const hasActivity = (key: string) => {
    const e = logs[key];
    return Boolean(e && (e.note.trim().length > 0 || e.completedQuestIds.length > 0));
  };

  const isToday = (d: Date) => toKey(d) === toKey(today);

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(280px,380px)]">
      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-md dark:border-slate-700 dark:bg-slate-800">
        <div className="flex items-center justify-between gap-2">
          <h2 className="inline-flex items-center gap-2 text-sm font-bold text-slate-900 dark:text-slate-100">
            <CalendarDays className="h-4 w-4 text-indigo-600" />
            성장 아카이브
          </h2>
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => setMonthOffset((x) => x - 1)}
              className="rounded-lg border border-slate-200 p-1.5 text-slate-600 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-900"
              aria-label="이전 달"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <span className="min-w-[120px] text-center text-xs font-semibold text-slate-800 dark:text-slate-200">
              {year}년 {month + 1}월
            </span>
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
        <p className="mt-2 text-xs text-slate-600 dark:text-slate-400">
          완료·기록이 있는 날은 민트/인디고 점으로 표시합니다. (포트폴리오 빌더 연계 예정)
        </p>

        <div className="mt-4 grid grid-cols-7 gap-1 text-center text-[11px] font-semibold text-slate-500 dark:text-slate-500">
          {WEEK_LABELS.map((w) => (
            <div key={w} className="py-1">
              {w}
            </div>
          ))}
        </div>
        <div className="mt-1 grid grid-cols-7 gap-1">
          {calendarCells.map(({ date, inMonth }) => {
            const key = toKey(date);
            const active = key === selectedKey;
            const dot = hasActivity(key);
            return (
              <button
                key={`${key}-${inMonth}`}
                type="button"
                onClick={() => setSelectedKey(key)}
                className={`relative flex min-h-[40px] flex-col items-center justify-center rounded-xl border text-xs font-semibold transition ${
                  !inMonth
                    ? "border-transparent text-slate-300"
                    : active
                      ? "border-indigo-300 bg-indigo-50 text-indigo-900"
                      : isToday(date)
                        ? "border-emerald-200 bg-emerald-50/50 text-slate-900"
                        : "border-slate-100 bg-slate-50/40 text-slate-800 hover:border-slate-200 hover:bg-white dark:border-slate-700 dark:bg-slate-900/60 dark:text-slate-300 dark:hover:bg-slate-900"
                }`}
              >
                <span>{date.getDate()}</span>
                {inMonth && dot ? (
                  <span
                    className={`mt-0.5 h-1.5 w-1.5 rounded-full ${
                      active ? "bg-indigo-500" : "bg-emerald-500"
                    }`}
                  />
                ) : (
                  <span className="mt-0.5 h-1.5 w-1.5" />
                )}
              </button>
            );
          })}
        </div>
      </section>

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
          <p className="text-xs font-semibold text-slate-600 dark:text-slate-400">이날 달성한 퀘스트</p>
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

        <div className="mt-4 flex-1">
          <label htmlFor="growth-log" className="text-xs font-semibold text-slate-600 dark:text-slate-400">
            배운 것 · 해결한 것 (마크다운 스타일 자유 기록)
          </label>
          <textarea
            id="growth-log"
            value={selectedLog.note}
            onChange={(e) => setNote(e.target.value)}
            rows={10}
            className="mt-2 w-full resize-y rounded-2xl border border-slate-200 bg-white p-3 text-sm text-slate-900 shadow-sm placeholder:text-slate-400 focus:border-indigo-300 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100 dark:placeholder:text-slate-500"
            placeholder="예: 오늘은 스키마에서 `scope3` 경계를 어떻게 끊을지 고민했다…"
          />
        </div>

        <motion.button
          type="button"
          whileTap={{ scale: 0.98 }}
          onClick={save}
          className="mt-4 inline-flex items-center justify-center gap-2 rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-indigo-700"
        >
          <Save className="h-4 w-4" />
          저장 (로컬)
        </motion.button>
      </section>
    </div>
  );
}
