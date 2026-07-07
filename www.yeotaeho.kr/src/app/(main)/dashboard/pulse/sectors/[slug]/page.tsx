"use client";

// 섹터 주간 트렌드 상세 페이지 — 펄스 카드 클릭 시 진입하는 드릴다운 뷰

import Link from "next/link";
import { useMemo } from "react";
import { useParams } from "next/navigation";

import { PanelStatus } from "@/components/features/dashboard/PanelStatus";
import { toWeeklyPoints, WeeklyTrendChart } from "@/components/features/dashboard/PulseWeeklyTrend";
import { Sparkline, TrendStatusBadge } from "@/components/features/dashboard/PulseViz";
import { usePulse, usePulseHistory } from "@/hooks/useDashboard";

function StatCard({ label, value, spark }: { label: string; value: string; spark?: number[] }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-700 dark:bg-slate-900">
      <div>
        <p className="text-2xl font-bold text-slate-900 dark:text-slate-100">{value}</p>
        <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">{label}</p>
      </div>
      {spark && spark.length >= 2 && <Sparkline values={spark} className="w-20 h-8 shrink-0" />}
    </div>
  );
}

export default function PulseSectorDetailPage() {
  const params = useParams();
  const slug = String(params?.slug ?? "");
  const { data: history, isLoading, isError } = usePulseHistory(slug || undefined);
  const { data: livePulse } = usePulse();
  const live = (livePulse ?? []).find((s) => s.sector_slug === slug);
  const weekly = useMemo(() => toWeeklyPoints(history?.points ?? []), [history]);
  const weeklyValues = weekly.map((p) => p.value);

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs font-semibold text-indigo-600">실시간 펄스 · 섹터 상세</p>
        <div className="mt-1 flex items-center gap-2.5 flex-wrap">
          <h1 className="text-2xl sm:text-3xl font-bold text-slate-900 dark:text-slate-100">
            {history?.sector_name ?? live?.sector_name ?? "섹터"}
          </h1>
          <TrendStatusBadge momentum={live?.momentum_pct} />
          {live?.momentum_pct != null && (
            <span
              className={`text-sm font-bold ${live.momentum_pct < 0 ? "text-rose-600" : "text-emerald-600"}`}
            >
              {live.momentum_pct > 0 ? "+" : ""}
              {live.momentum_pct}%
            </span>
          )}
        </div>
        <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">
          최근 {weekly.length}주간의 주 평균 트렌드 점수 추이입니다.
        </p>
      </div>

      <PanelStatus isLoading={isLoading} isError={isError} isEmpty={weekly.length === 0} label="주간 트렌드">
        <div className="space-y-6">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <StatCard label="현재 점수" value={String(live?.score ?? weeklyValues[weeklyValues.length - 1] ?? "—")} spark={weeklyValues} />
            <StatCard label="주간 최고" value={String(weeklyValues.length ? Math.max(...weeklyValues) : "—")} />
            <StatCard label="주간 최저" value={String(weeklyValues.length ? Math.min(...weeklyValues) : "—")} />
          </div>

          <section className="rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-700 dark:bg-slate-900">
            <h2 className="text-base font-bold text-slate-800 dark:text-slate-100 mb-4">주간 트렌드</h2>
            <WeeklyTrendChart points={weekly} accent={live?.accent_color ?? null} />
          </section>
        </div>
      </PanelStatus>

      <div className="flex flex-wrap gap-3">
        <Link
          href="/"
          className="inline-flex items-center justify-center rounded-xl border border-slate-200 bg-white text-sm font-semibold px-4 py-2.5 text-slate-700 hover:bg-slate-50 transition dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800"
        >
          대시보드로
        </Link>
      </div>
    </div>
  );
}
