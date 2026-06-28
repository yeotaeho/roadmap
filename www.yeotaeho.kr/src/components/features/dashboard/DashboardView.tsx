"use client";

import React from "react";
import Link from "next/link";
import {
  Activity,
  Compass,
  Link2,
  MoveRight,
  Rocket,
  TrendingUp,
  Workflow,
} from "lucide-react";
import { useStore } from "@/store";
import { useGapIssues, useOpportunities, useSyncHistory, useSyncScores } from "@/hooks/useDashboard";
import { ddayLabel } from "@/lib/api/dashboard";
import { cn } from "@/lib/utils";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { PanelStatus } from "./PanelStatus";
import { PulseTab } from "./PulseTab";
import { Sparkline, SyncGauge } from "./PulseViz";

const SUB_TABS = [
  { id: "pulse", label: "펄스", fullLabel: "실시간 펄스", icon: Activity },
  { id: "gap", label: "블루오션", fullLabel: "블루오션", icon: Compass },
  { id: "sync", label: "싱크", fullLabel: "싱크로율", icon: Link2 },
  { id: "chance", label: "찬스", fullLabel: "다이렉트 찬스", icon: Rocket },
] as const;

export function DashboardView() {
  return (
    <div className="space-y-7">
      <div>
        <h1 className="text-2xl sm:text-3xl font-bold text-slate-900 dark:text-slate-100">
          인사이트 대시보드
        </h1>
        <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
          지금의 흐름, 기회, 나와의 연결, 당장의 행동을 한곳에서 확인하세요.
        </p>
      </div>

      <Tabs defaultValue="pulse">
        <TabsList className="flex flex-wrap h-auto gap-1 p-1.5 bg-indigo-50/70 rounded-2xl border border-indigo-100 dark:bg-slate-900 dark:border-slate-700">
          {SUB_TABS.map(({ id, label, fullLabel, icon: Icon }) => (
            <TabsTrigger
              key={id}
              value={id}
              className={cn(
                "flex items-center gap-2 rounded-xl px-3 sm:px-4 py-2.5 text-sm font-medium transition",
                "text-slate-600 dark:text-slate-300",
                "data-[state=active]:bg-white data-[state=active]:text-indigo-700 data-[state=active]:shadow-sm data-[state=active]:ring-1 data-[state=active]:ring-indigo-100",
                "dark:data-[state=active]:bg-slate-800 dark:data-[state=active]:text-indigo-300 dark:data-[state=active]:ring-slate-700",
                "hover:text-indigo-700 hover:bg-white/70 dark:hover:text-indigo-300 dark:hover:bg-slate-800/80"
              )}
            >
              <Icon className="w-4 h-4 shrink-0" aria-hidden />
              <span className="hidden sm:inline">{fullLabel}</span>
              <span className="sm:hidden">{label}</span>
            </TabsTrigger>
          ))}
        </TabsList>

        <div className="mt-2 rounded-2xl border border-slate-200 bg-white p-4 sm:p-6 shadow-[0_8px_30px_rgba(15,23,42,0.08)] min-h-[420px] dark:border-slate-700 dark:bg-slate-900 dark:shadow-none">
          <TabsContent value="pulse" className="mt-0">
            <PulseTab />
          </TabsContent>
          <TabsContent value="gap" className="mt-0">
            <GapPanel />
          </TabsContent>
          <TabsContent value="sync" className="mt-0">
            <SyncPanel />
          </TabsContent>
          <TabsContent value="chance" className="mt-0">
            <ChancePanel />
          </TabsContent>
        </div>
      </Tabs>

      <p className="text-center text-xs text-slate-500 dark:text-slate-400">
        모든 데이터는 백엔드 실시간 연동입니다. 실데이터가 없거나 실패하면 에러로 표시됩니다.
      </p>
    </div>
  );
}

function GapPanel() {
  const { data, isLoading, isError } = useGapIssues();
  const items = data ?? [];
  return (
    <div className="space-y-4">
      <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100">블루오션 (세상의 결핍)</h2>
      <PanelStatus isLoading={isLoading} isError={isError} isEmpty={items.length === 0} label="블루오션">
        <div className="space-y-3">
          {items.map((card) => (
            <article key={card.id} className="rounded-2xl overflow-hidden border border-slate-200 dark:border-slate-700">
              <div className="grid sm:grid-cols-2">
                <div className="bg-slate-900 text-white p-4">
                  <p className="text-xs text-slate-300">세상의 문제</p>
                  <p className="mt-2 text-sm font-medium">{card.problem_summary}</p>
                </div>
                <div className="bg-emerald-50 p-4 border-t sm:border-t-0 sm:border-l border-emerald-100 dark:bg-emerald-900/20 dark:border-emerald-900/40">
                  <p className="text-xs text-emerald-700">청년의 기회</p>
                  <p className="mt-2 text-sm font-semibold text-emerald-900">{card.chance_summary}</p>
                </div>
              </div>
              <div className="px-4 py-3 bg-white border-t border-slate-100 dark:bg-slate-900 dark:border-slate-700">
                <Link
                  href={`/dashboard/gap/issues/${card.id}`}
                  className="inline-flex items-center gap-1 text-sm font-medium text-indigo-600 hover:text-indigo-700"
                >
                  이 분야 파고들기 <MoveRight className="w-4 h-4" />
                </Link>
              </div>
            </article>
          ))}
        </div>
      </PanelStatus>
    </div>
  );
}

type SyncRow = { trend: string; score: number; badge?: string };

function SyncPanel() {
  const profile = useStore((s) => s.profile);
  const { data, isLoading, isError } = useSyncScores(profile?.id);
  const { data: history } = useSyncHistory(profile?.id);
  const needsLogin = !profile?.id;
  const trendSync: SyncRow[] = (data ?? []).map((s) => ({
    trend: s.sector_name,
    score: s.score,
    badge: s.badge ?? undefined,
  }));
  const overall = trendSync.length
    ? Math.round(trendSync.reduce((acc, r) => acc + r.score, 0) / trendSync.length)
    : 0;
  const trajectory = (history ?? []).map((h) => h.score);
  const delta = trajectory.length >= 2 ? trajectory[trajectory.length - 1] - trajectory[0] : null;

  return (
    <div className="space-y-4">
      <section className="rounded-2xl border border-slate-200 bg-white p-4 sm:p-5 shadow-sm dark:border-slate-700 dark:bg-slate-800">
        <div className="flex items-center justify-between gap-2">
          <h3 className="text-sm font-semibold text-slate-800 inline-flex items-center gap-2 dark:text-slate-100">
            <TrendingUp className="w-4 h-4 text-indigo-600" aria-hidden />
            트렌드 대비 싱크로율
          </h3>
          <span className="text-[11px] text-slate-400 dark:text-slate-500">실시간 연동</span>
        </div>
        <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
          선택한 관심 키워드와 도메인별 시장 신호를 비교해 일치 정도를 보여줍니다.
        </p>
        {needsLogin ? (
          <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-6 text-center text-sm text-slate-500 dark:border-slate-700 dark:bg-slate-900/50 dark:text-slate-400">
            로그인하면 나의 관심·직무 기준 섹터 싱크로율을 볼 수 있습니다.
          </div>
        ) : (
          <PanelStatus
            isLoading={isLoading}
            isError={isError}
            isEmpty={trendSync.length === 0}
            label="싱크로율"
          >
            <div className="mt-4 flex items-center gap-4 rounded-xl border border-indigo-100 bg-indigo-50/40 p-4 dark:border-indigo-900/40 dark:bg-indigo-900/10">
              <SyncGauge value={overall} />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-bold text-slate-900 dark:text-slate-100">나와의 싱크 {overall}%</p>
                <p className="mt-1 text-xs text-slate-600 dark:text-slate-300 leading-relaxed">
                  관심·직무 기준 섹터 적합도. {trendSync[0]?.trend}가 당신과 가장 정렬됐어요.
                  {delta != null && delta !== 0 && (
                    <span className={delta > 0 ? "text-emerald-600" : "text-rose-600"}>
                      {" "}지난 추이 {delta > 0 ? "+" : ""}{delta}p.
                    </span>
                  )}
                </p>
              </div>
              {trajectory.length >= 2 && (
                <Sparkline values={trajectory} width={84} height={32} className="w-20 h-8 shrink-0" />
              )}
            </div>
            <ul className="mt-4 space-y-3">
              {trendSync.map((row) => (
                <li
                  key={row.trend}
                  className="rounded-xl border border-slate-100 bg-slate-50/70 p-3 dark:border-slate-700 dark:bg-slate-900/50"
                >
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-sm font-medium text-slate-800 leading-snug dark:text-slate-100">{row.trend}</p>
                    <div className="shrink-0 text-right flex items-center gap-2">
                      {row.badge && (
                        <Badge variant="secondary" className="text-[11px] text-indigo-600 dark:text-indigo-300">
                          {row.badge}
                        </Badge>
                      )}
                      <p className="text-lg font-bold text-indigo-700">{row.score}</p>
                    </div>
                  </div>
                  <Progress
                    value={row.score}
                    className="mt-2 h-2 bg-slate-200 dark:bg-slate-700 [&>div]:bg-gradient-to-r [&>div]:from-indigo-500 [&>div]:to-emerald-400"
                  />
                </li>
              ))}
            </ul>
          </PanelStatus>
        )}
      </section>
    </div>
  );
}

function ChancePanel() {
  const { data, isLoading, isError } = useOpportunities();
  const items = data ?? [];
  return (
    <div className="space-y-4">
      <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100">다이렉트 찬스</h2>
      <PanelStatus isLoading={isLoading} isError={isError} isEmpty={items.length === 0} label="다이렉트 찬스">
        <div className="flex gap-3 overflow-x-auto pb-1 scrollbar-hide">
          {items.map((item, idx) => (
            <article
              key={item.id}
              className={cn(
                "min-w-[280px] max-w-[320px] rounded-2xl border bg-white p-4 shadow-sm dark:bg-slate-800",
                idx === 0
                  ? "border-violet-200 shadow-[0_0_0_2px_rgba(139,92,246,0.15)] dark:border-violet-900/50"
                  : "border-slate-200 dark:border-slate-700"
              )}
            >
              <div className="flex items-start justify-between gap-2">
                <Badge className="bg-indigo-50 text-indigo-700 hover:bg-indigo-50 dark:bg-indigo-900/30 dark:text-indigo-300 border-0 font-semibold">
                  {item.opportunity_type ?? "공고"}
                </Badge>
                {item.host_name && (
                  <span className="text-xs font-medium text-slate-500 truncate max-w-[140px] dark:text-slate-400">
                    {item.host_name}
                  </span>
                )}
              </div>
              <p className="mt-3 text-sm font-semibold text-slate-900 dark:text-slate-100">{item.title}</p>
              <p className="mt-2 text-xs text-violet-700 font-bold dark:text-violet-300">{ddayLabel(item.d_day_date)}</p>
              <div className="mt-4 flex items-center justify-between">
                <button
                  type="button"
                  className="text-xs font-medium text-slate-600 bg-slate-100 px-2.5 py-1 rounded-full dark:bg-slate-700 dark:text-slate-300"
                >
                  저장
                </button>
                <Link
                  href={`/dashboard/chance/opportunities/${item.id}`}
                  className="text-xs font-medium text-indigo-600 hover:text-indigo-700 inline-flex items-center gap-1 dark:text-indigo-300 dark:hover:text-indigo-200"
                >
                  자세히 보기 <MoveRight className="w-3.5 h-3.5" />
                </Link>
              </div>
            </article>
          ))}
        </div>
      </PanelStatus>
      <Link
        href="/coach"
        className="inline-flex text-sm font-medium text-indigo-600 hover:text-indigo-700 items-center gap-1 dark:text-indigo-300 dark:hover:text-indigo-200"
      >
        AI 코치에게 이 기회에 대해 물어보기 <Workflow className="w-4 h-4" />
      </Link>
    </div>
  );
}
