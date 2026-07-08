"use client";

// 여정 개요 — 여정 지도(게임 스테이지 맵) + 역량 3축 칩 + 직무 키워드 브릿지

import { Hexagon, Map as MapIcon, Sparkles } from "lucide-react";
import { useMemo } from "react";
import { BRIDGE_KEYWORDS, QUEST_TREE, SKILL_TRIANGLE } from "@/data/roadmapQuestMap";
import { usePlannerBoard } from "@/hooks/usePlanner";
import { useJourney, useRefreshRoadmap } from "@/hooks/useRoadmap";
import { useStore } from "@/store";
import { JourneyQuestMap } from "./JourneyQuestMap";

export function JourneyMapTab() {
  const profile = useStore((s) => s.profile);
  const loggedIn = !!profile?.id;
  const { data, isLoading } = useJourney(loggedIn);
  const refresh = useRefreshRoadmap();
  const { data: plannerData } = usePlannerBoard(loggedIn);

  // 로그인 사용자에게 생성된 로드맵이 있으면 라이브, 없으면 로컬 목업으로 폴백.
  const pillars = data?.roadmap?.skillPillars ?? SKILL_TRIANGLE;
  const bridge = data?.roadmap?.bridgeKeywords ?? BRIDGE_KEYWORDS;
  const tree = data?.questTree ?? QUEST_TREE;
  const isLive = Boolean(data?.questTree);

  const taskCounts = useMemo(() => {
    const m = new Map<string, { done: number; total: number }>();
    for (const t of plannerData?.tasks ?? []) {
      if (!t.questKey) continue;
      const cur = m.get(t.questKey) ?? { done: 0, total: 0 };
      cur.total += 1;
      if (t.status === "done") cur.done += 1;
      m.set(t.questKey, cur);
    }
    return m;
  }, [plannerData]);

  return (
    <div className="space-y-8 pb-4">
      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-md dark:border-slate-700 dark:bg-slate-800">
        <div className="flex flex-wrap items-end justify-between gap-2">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-500">
              여정 지도
            </p>
            <h2 className="mt-1 inline-flex items-center gap-2 text-lg font-bold text-slate-900 dark:text-slate-100">
              <MapIcon className="h-5 w-5 text-indigo-600" />
              퀘스트 월드맵
            </h2>
            <p className="mt-1 max-w-xl text-sm text-slate-600 dark:text-slate-400">
              시작점에서 갈래로 뻗는 과제 지도입니다. 스테이지를 눌러 <strong className="text-slate-800 dark:text-slate-200">현재 위치</strong>를 옮기며 다음 목표를 살펴보세요.
            </p>
          </div>
          <div className="flex items-center gap-2">
            {isLoading ? (
              <span className="text-[11px] text-slate-400">불러오는 중…</span>
            ) : !isLive ? (
              <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-500 dark:bg-slate-800 dark:text-slate-400">
                예시 로드맵
              </span>
            ) : null}
            {loggedIn ? (
              <button
                type="button"
                onClick={() => refresh.mutate()}
                disabled={refresh.isPending}
                className="inline-flex items-center gap-1.5 rounded-xl bg-indigo-600 px-3 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-indigo-700 disabled:opacity-60"
              >
                <Sparkles className="h-4 w-4" />
                {refresh.isPending ? "생성 중…" : isLive ? "로드맵 다시 생성" : "내 로드맵 생성"}
              </button>
            ) : null}
          </div>
        </div>

        {/* 역량 3축 칩 (구 스킬 트라이앵글) */}
        <div className="mt-4 flex flex-wrap gap-2">
          {pillars.map((p) => (
            <span
              key={p.id}
              title={p.blurb}
              className="inline-flex items-center gap-1.5 rounded-full border border-indigo-100 bg-indigo-50 px-3 py-1.5 text-xs font-semibold text-indigo-800 dark:border-indigo-900/40 dark:bg-indigo-900/20 dark:text-indigo-300"
            >
              <Hexagon className="h-3.5 w-3.5 text-indigo-500" />
              {p.label}
            </span>
          ))}
        </div>

        {loggedIn && !isLive && !isLoading ? (
          <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
            프로필의 역량 정보를 바탕으로 나만의 로드맵을 생성합니다. (아래는 예시)
          </p>
        ) : null}

        <div className="mt-5">
          <JourneyQuestMap tree={tree} taskCounts={isLive ? taskCounts : undefined} />
        </div>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-800">
        <p className="text-xs font-semibold text-slate-500 dark:text-slate-500">직무 키워드 브릿지</p>
        <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
          대시보드 트렌드와 상담 결과를 잇는 태그입니다.
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          {bridge.map((k) => (
            <span
              key={k}
              className="rounded-full border border-indigo-100 bg-indigo-50 px-3 py-1.5 text-xs font-semibold text-indigo-800 dark:border-indigo-900/40 dark:bg-indigo-900/20 dark:text-indigo-300"
            >
              {k}
            </span>
          ))}
        </div>
      </section>
    </div>
  );
}
