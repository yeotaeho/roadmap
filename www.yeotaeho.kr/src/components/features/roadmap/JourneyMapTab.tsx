"use client";

import { motion } from "framer-motion";
import { Hexagon, Sparkles, Triangle } from "lucide-react";
import type { QuestTreeNode } from "@/data/roadmapQuestMap";
import {
  BRIDGE_KEYWORDS,
  QUEST_TREE,
  SKILL_TRIANGLE,
} from "@/data/roadmapQuestMap";

const DIFFICULTY_RING: Record<string, string> = {
  입문: "ring-emerald-200 bg-emerald-50 text-emerald-800",
  중급: "ring-amber-200 bg-amber-50 text-amber-900",
  심화: "ring-violet-200 bg-violet-50 text-violet-900",
};

const STATE_STYLE: Record<string, string> = {
  start: "border-indigo-300 bg-indigo-50/80 shadow-md shadow-indigo-100/60 dark:border-indigo-800 dark:bg-indigo-900/20 dark:shadow-none",
  done: "border-emerald-200 bg-white dark:border-emerald-900/40 dark:bg-slate-800",
  active: "border-indigo-400 bg-white ring-2 ring-indigo-200/70 dark:border-indigo-700 dark:bg-slate-800 dark:ring-indigo-900/40",
  available: "border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-800",
  locked: "border-slate-100 bg-slate-50 opacity-75 dark:border-slate-700 dark:bg-slate-900",
};

function QuestTreeCard({ node, depth }: { node: QuestTreeNode; depth: number }) {
  const isRoot = node.state === "start";

  return (
    <div className={depth > 0 ? "mt-3 border-l-2 border-slate-200 pl-4 dark:border-slate-700" : ""}>
      <motion.article
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: depth * 0.05 }}
        className={`rounded-2xl border p-4 shadow-sm transition ${STATE_STYLE[node.state] ?? STATE_STYLE.available}`}
      >
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">{node.title}</h3>
            <p className="mt-1 text-xs leading-relaxed text-slate-600 dark:text-slate-400">{node.purpose}</p>
          </div>
          <div className="flex shrink-0 flex-col items-end gap-1">
            <span
              className={`rounded-full px-2 py-0.5 text-[10px] font-bold ring-1 ${DIFFICULTY_RING[node.difficulty]}`}
            >
              {node.difficulty}
            </span>
            {isRoot ? (
              <span className="inline-flex items-center gap-0.5 rounded-full bg-indigo-100 px-2 py-0.5 text-[10px] font-semibold text-indigo-800 dark:bg-indigo-900/35 dark:text-indigo-300">
                <Sparkles className="h-3 w-3" />
                시작점
              </span>
            ) : null}
          </div>
        </div>
        <div className="mt-3 flex flex-wrap gap-1.5">
          {node.keywords.map((kw) => (
            <span
              key={kw}
              className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-700 dark:bg-slate-700 dark:text-slate-300"
            >
              #{kw}
            </span>
          ))}
        </div>
      </motion.article>
      {node.children?.length ? (
        <div className="space-y-1">
          {node.children.map((ch) => (
            <QuestTreeCard key={ch.id} node={ch} depth={depth + 1} />
          ))}
        </div>
      ) : null}
    </div>
  );
}

export function JourneyMapTab() {
  return (
    <div className="space-y-8 pb-4">
      <section className="rounded-2xl border border-slate-200 bg-[#F8FAFC] p-6 shadow-sm dark:border-slate-700 dark:bg-slate-900">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-500">
          스킬 트라이앵글
        </p>
        <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
          획득해야 할 핵심 3축입니다. 일정이 아니라 <strong className="text-slate-800 dark:text-slate-200">역량 방향</strong>
          을 먼저 고정합니다.
        </p>

        <div className="relative mx-auto mt-8 max-w-md pb-6">
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="rounded-2xl border border-indigo-200 bg-white px-4 py-3 text-center shadow-sm dark:border-indigo-900/40 dark:bg-slate-800">
              <Triangle className="mx-auto h-5 w-5 text-indigo-500 dark:text-indigo-300" />
              <p className="mt-1 text-xs font-semibold text-indigo-700 dark:text-indigo-300">YOU</p>
              <p className="text-[11px] text-slate-500 dark:text-slate-500">지금 여기</p>
            </div>
          </div>

          <div className="relative h-52">
            {SKILL_TRIANGLE.map((s, i) => {
              const pos =
                i === 0
                  ? "left-1/2 top-0 -translate-x-1/2"
                  : i === 1
                    ? "bottom-0 left-0"
                    : "bottom-0 right-0";
              return (
                <motion.div
                  key={s.id}
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: 0.1 + i * 0.08 }}
                  className={`absolute max-w-[140px] rounded-2xl border border-white bg-white p-3 shadow-md dark:border-slate-700 dark:bg-slate-800 ${pos}`}
                >
                  <Hexagon className="h-4 w-4 text-indigo-500" />
                  <p className="mt-1 text-xs font-bold text-slate-900 dark:text-slate-100">{s.label}</p>
                  <p className="mt-1 text-[11px] leading-snug text-slate-600 dark:text-slate-400">{s.blurb}</p>
                </motion.div>
              );
            })}
          </div>
        </div>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-800">
        <p className="text-xs font-semibold text-slate-500 dark:text-slate-500">직무 키워드 브릿지</p>
        <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
          대시보드 트렌드와 상담 결과를 잇는 태그입니다.
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          {BRIDGE_KEYWORDS.map((k) => (
            <span
              key={k}
              className="rounded-full border border-indigo-100 bg-indigo-50 px-3 py-1.5 text-xs font-semibold text-indigo-800 dark:border-indigo-900/40 dark:bg-indigo-900/20 dark:text-indigo-300"
            >
              {k}
            </span>
          ))}
        </div>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-md dark:border-slate-700 dark:bg-slate-800">
        <div className="flex flex-wrap items-end justify-between gap-2">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-500">
              퀘스트 트리
            </p>
            <h2 className="mt-1 text-lg font-bold text-slate-900 dark:text-slate-100">과제 맵 (Quest Tree)</h2>
            <p className="mt-1 max-w-xl text-sm text-slate-600 dark:text-slate-400">
              시작점에서 가지처럼 퍼지는 과제들입니다. 잠금(회색)은 앞 단계를 밟으면 열립니다.
            </p>
          </div>
        </div>
        <div className="mt-6">
          <QuestTreeCard node={QUEST_TREE} depth={0} />
        </div>
      </section>
    </div>
  );
}
