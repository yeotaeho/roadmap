"use client";

import Link from "next/link";
import { AnimatePresence, motion } from "framer-motion";
import { Compass, Map, Route } from "lucide-react";
import { GrowthArchiveTab } from "./GrowthArchiveTab";
import { JourneyMapTab } from "./JourneyMapTab";
import { useRoadmapNav } from "./RoadmapNavContext";

export function RoadmapView() {
  // 좌측 사이드바(셸)와 공유하는 서브탭 상태.
  const { subTab } = useRoadmapNav();

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
