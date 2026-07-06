"use client";

import Link from "next/link";
import { AnimatePresence, motion } from "framer-motion";
import { Compass } from "lucide-react";
import { GrowthArchiveTab } from "./GrowthArchiveTab";
import { JourneyMapTab } from "./JourneyMapTab";
import { PlannerTab } from "./planner/PlannerTab";
import { useRoadmapNav } from "./RoadmapNavContext";

export function RoadmapView() {
  // 좌측 사이드바(셸)와 공유하는 서브탭 상태.
  const { subTab } = useRoadmapNav();

  return (
    <div className="min-h-[calc(100vh-220px)] space-y-6">
      <AnimatePresence mode="wait">
        <motion.div
          key={subTab}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -6 }}
          transition={{ duration: 0.2 }}
        >
          {subTab === "journey" ? (
            <JourneyMapTab />
          ) : subTab === "planner" ? (
            <PlannerTab />
          ) : (
            <GrowthArchiveTab />
          )}
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
