"use client";

import Link from "next/link";
import { AnimatePresence, motion } from "framer-motion";
import { Compass, Map, Route } from "lucide-react";
import { useState } from "react";
import { GrowthArchiveTab } from "./GrowthArchiveTab";
import { JourneyMapTab } from "./JourneyMapTab";

type RoadmapSubTab = "journey" | "archive";

const SUB_TABS: { id: RoadmapSubTab; label: string; hint: string }[] = [
  { id: "journey", label: "여정 개요", hint: "Journey Map" },
  { id: "archive", label: "성장 아카이브", hint: "Growth Calendar" },
];

export function RoadmapView() {
  const [subTab, setSubTab] = useState<RoadmapSubTab>("journey");

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="rounded-xl bg-indigo-100 p-3 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-300">
            <Route className="h-6 w-6" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">전략 로드맵</h1>
            <p className="mt-1 max-w-xl text-sm text-slate-600 dark:text-slate-400">
              일정 감시가 아니라,{" "}
              <strong className="font-semibold text-slate-800 dark:text-slate-200">기회(퀘스트) 지도</strong>와{" "}
              <strong className="font-semibold text-slate-800 dark:text-slate-200">성장 기록</strong>을 나란히 둡니다.
            </p>
            <p className="mt-1 text-xs text-slate-500 dark:text-slate-500">
              목표 브릿지: 에너지·ESG × AI 엔지니어링 (방향만 고정, 마감은 강제하지 않음)
            </p>
          </div>
        </div>
        <div className="inline-flex items-center gap-1 rounded-xl border border-slate-200 bg-slate-50 px-2 py-1 text-[11px] text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300">
          <Map className="h-3.5 w-3.5 text-indigo-500 dark:text-indigo-300" />
          L2 서브탭 2종
        </div>
      </header>

      <nav
        className="flex gap-1 rounded-2xl border border-slate-200 bg-[#F8FAFC] p-1 shadow-sm dark:border-slate-700 dark:bg-slate-900"
        aria-label="로드맵 하위 탭"
      >
        {SUB_TABS.map((t) => {
          const active = subTab === t.id;
          return (
            <button
              key={t.id}
              type="button"
              onClick={() => setSubTab(t.id)}
              className={`relative flex-1 rounded-xl px-3 py-2.5 text-left transition ${
                active
                  ? "bg-white text-slate-900 shadow-sm ring-1 ring-slate-200/80 dark:bg-slate-800 dark:text-slate-100 dark:ring-slate-700"
                  : "text-slate-600 hover:text-slate-900 dark:text-slate-300 dark:hover:text-slate-100"
              }`}
            >
              <span className="block text-sm font-bold">{t.label}</span>
              <span className="block text-[11px] text-slate-500 dark:text-slate-500">{t.hint}</span>
              {active ? (
                <motion.span
                  layoutId="roadmapSubTabIndicator"
                  className="absolute bottom-1 left-3 right-3 h-0.5 rounded-full bg-indigo-600"
                />
              ) : null}
            </button>
          );
        })}
      </nav>

      <AnimatePresence mode="wait">
        <motion.div
          key={subTab}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -6 }}
          transition={{ duration: 0.2 }}
        >
          {subTab === "journey" ? <JourneyMapTab /> : <GrowthArchiveTab />}
        </motion.div>
      </AnimatePresence>

      <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-800">
        <p className="inline-flex items-center gap-2 text-xs font-semibold text-slate-600 dark:text-slate-300">
          <Compass className="h-4 w-4 text-indigo-600" />
          다음 액션
        </p>
        <div className="mt-3 flex flex-wrap gap-2 text-sm">
          <Link
            href="/consult"
            className="rounded-xl border border-indigo-200 bg-indigo-50 px-3 py-2 font-semibold text-indigo-700 transition hover:bg-indigo-100 dark:border-indigo-900/40 dark:bg-indigo-900/20 dark:text-indigo-300 dark:hover:bg-indigo-900/35"
          >
            AI 상담실
          </Link>
          <Link
            href="/coach"
            className="rounded-xl border border-slate-200 bg-white px-3 py-2 font-semibold text-slate-700 transition hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800"
          >
            AI 코치
          </Link>
          <Link
            href="/"
            className="rounded-xl border border-slate-200 bg-white px-3 py-2 font-semibold text-slate-700 transition hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800"
          >
            인사이트 대시보드
          </Link>
        </div>
      </section>
    </div>
  );
}
