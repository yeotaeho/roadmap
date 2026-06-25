"use client";

/**
 * 실시간 펄스(Pulse) 탭 — 섹터 카드 + 속도계·모멘텀·히트맵·점유율(Pulse Gold 즉석 집계).
 */

import { usePulse, usePulseOverview } from "@/hooks/useDashboard";
import type { PulseHeatmapRow, PulseMomentumPoint } from "@/lib/api/dashboard";
import { PanelStatus } from "./PanelStatus";

function heatTone(score: number | null): string {
  if (score == null) return "bg-slate-100 text-slate-400 dark:bg-slate-700 dark:text-slate-500";
  if (score >= 85) return "bg-indigo-600 text-white";
  if (score >= 70) return "bg-indigo-400 text-white";
  if (score >= 55) return "bg-indigo-200 text-indigo-900";
  return "bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-200";
}

// 신호가 빈약해 전 구간 중립(50)으로 게이트된 섹터 표식.
function DataPendingBadge() {
  return (
    <span className="ml-1.5 align-middle text-[9px] px-1.5 py-0.5 rounded-full bg-slate-200 text-slate-500 dark:bg-slate-700 dark:text-slate-400 whitespace-nowrap">
      데이터 수집 중
    </span>
  );
}

function MomentumChart({ points }: { points: PulseMomentumPoint[] }) {
  if (points.length === 0) {
    return <p className="text-sm text-slate-400">시계열 데이터가 아직 없습니다.</p>;
  }
  const w = 560;
  const h = 160;
  const max = Math.max(...points.map((p) => p.value), 1);
  const min = Math.min(...points.map((p) => p.value), 0);
  const span = max - min || 1;
  const xAt = (i: number) => (points.length === 1 ? w / 2 : (i / (points.length - 1)) * w);
  const yAt = (v: number) => h - ((v - min) / span) * h;
  const line = points.map((p, i) => `${i === 0 ? "M" : "L"}${xAt(i)},${yAt(p.value)}`).join(" ");
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-52" role="img" aria-label="연간 모멘텀 트렌드 차트">
      <path d={`${line} L${xAt(points.length - 1)},${h} L${xAt(0)},${h} Z`} fill="#6366f1" fillOpacity="0.12" />
      <path d={line} fill="none" stroke="#6366f1" strokeWidth="2" />
      {points.map((p, i) => (
        <circle key={p.bucket} cx={xAt(i)} cy={yAt(p.value)} r="2.5" fill="#6366f1" />
      ))}
    </svg>
  );
}

function Heatmap({ buckets, rows }: { buckets: string[]; rows: PulseHeatmapRow[] }) {
  if (buckets.length === 0 || rows.length === 0) {
    return <p className="text-sm text-slate-400">히트맵 데이터가 아직 없습니다.</p>;
  }
  return (
    <div className="overflow-x-auto">
      <table className="border-separate" style={{ borderSpacing: "4px" }}>
        <thead>
          <tr>
            <th className="text-left text-xs font-medium text-slate-400 pr-2" />
            {buckets.map((b) => (
              <th key={b} className="text-[10px] font-medium text-slate-400 text-center">
                {b}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.sector_slug}>
              <td className="text-xs font-medium pr-2 whitespace-nowrap">
                <span
                  className={
                    row.data_status === "insufficient"
                      ? "text-slate-400 dark:text-slate-500"
                      : "text-slate-600 dark:text-slate-300"
                  }
                >
                  {row.sector_name}
                </span>
                {row.data_status === "insufficient" && <DataPendingBadge />}
              </td>
              {row.cells.map((c) => (
                <td
                  key={`${row.sector_slug}-${c.bucket}`}
                  className={`h-8 w-12 rounded text-center text-[11px] font-semibold ${heatTone(c.score)}`}
                  title={`${row.sector_name} / ${c.bucket} / ${c.score ?? "—"}`}
                >
                  {c.score ?? "—"}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function PulseTab() {
  const { data: livePulse, isLoading, isError } = usePulse();
  const { data: overview, isLoading: ovLoading, isError: ovError } = usePulseOverview();

  const sectorCards = (livePulse ?? []).map((s) => ({
    slug: s.sector_slug,
    title: s.sector_name,
    status: s.status_badge,
    score: s.score,
    momentum: s.momentum_pct,
    accent: s.accent_color as string | null,
  }));

  const g = overview?.gauge;
  const insufficientSlugs = new Set(
    (overview?.heatmap.rows ?? [])
      .filter((r) => r.data_status === "insufficient")
      .map((r) => r.sector_slug),
  );

  return (
    <div className="w-full flex flex-col gap-6 font-sans">
      {/* 1. 속도계 / 주간지수 */}
      <PanelStatus isLoading={ovLoading} isError={ovError} isEmpty={!g} label="트렌드 속도계">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-1 rounded-2xl bg-indigo-600 text-white p-6 flex flex-col justify-between">
            <span className="text-sm font-medium text-indigo-100">트렌드 속도계</span>
            <div className="flex items-end gap-1 mt-2">
              <span className="text-5xl font-extrabold tracking-tight">{g?.speed_kmh ?? "—"}</span>
              <span className="text-lg mb-1">km/h</span>
            </div>
            <div className="mt-3 flex items-center justify-between text-sm">
              <span>주간 지수 {g?.weekly_index ?? "—"} / 100</span>
              {g?.day_delta_pct != null && (
                <span className={g.day_delta_pct < 0 ? "text-rose-200" : "text-emerald-200"}>
                  {g.day_delta_pct > 0 ? "+" : ""}
                  {g.day_delta_pct}%
                </span>
              )}
            </div>
          </div>
          <div className="lg:col-span-2 rounded-2xl border border-slate-200 dark:border-slate-700 p-6">
            <h3 className="text-sm font-semibold text-slate-500 dark:text-slate-400 mb-1">오늘의 모멘텀 리더</h3>
            {g?.top_mover ? (
              <p className="text-lg font-bold text-slate-800 dark:text-slate-100">
                {g.top_mover.sector_name}{" "}
                <span className="text-emerald-600">+{g.top_mover.momentum_pct}%</span>
              </p>
            ) : (
              <p className="text-sm text-slate-400">모멘텀 신호가 아직 없습니다.</p>
            )}
          </div>
        </div>
      </PanelStatus>

      {/* 2. 연간 모멘텀 + 관심 점유율 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 lg:items-start">
        <section className="lg:col-span-2 rounded-2xl border border-slate-200 dark:border-slate-700 p-6">
          <h2 className="text-base font-bold text-slate-800 dark:text-slate-100 mb-4">연간 모멘텀 트렌드</h2>
          <PanelStatus
            isLoading={ovLoading}
            isError={ovError}
            isEmpty={(overview?.momentum_series.length ?? 0) === 0}
            label="모멘텀"
          >
            <MomentumChart points={overview?.momentum_series ?? []} />
          </PanelStatus>
        </section>
        <section className="rounded-2xl border border-slate-200 dark:border-slate-700 p-6">
          <h2 className="text-base font-bold text-slate-800 dark:text-slate-100 mb-4">관심 점유율</h2>
          <PanelStatus
            isLoading={ovLoading}
            isError={ovError}
            isEmpty={(overview?.share.length ?? 0) === 0}
            label="점유율"
          >
            <div className="flex flex-col gap-2">
              {(overview?.share ?? []).map((s) => (
                <div key={s.sector_slug}>
                  <div className="flex justify-between text-xs text-slate-600 dark:text-slate-300 mb-0.5">
                    <span>{s.sector_name}</span>
                    <span>{s.pct}%</span>
                  </div>
                  <div className="w-full bg-slate-200 dark:bg-slate-700 h-2 rounded-full overflow-hidden">
                    <div className="h-full bg-indigo-500" style={{ width: `${s.pct}%` }} />
                  </div>
                </div>
              ))}
            </div>
          </PanelStatus>
        </section>
      </div>

      {/* 3. 섹터 × 시간 히트맵 */}
      <section className="rounded-2xl border border-slate-200 dark:border-slate-700 p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-bold text-slate-800 dark:text-slate-100">Top 섹터 히트맵</h2>
          <span className="text-xs text-slate-400">분야 × 시간</span>
        </div>
        <PanelStatus
          isLoading={ovLoading}
          isError={ovError}
          isEmpty={(overview?.heatmap.rows.length ?? 0) === 0}
          label="히트맵"
        >
          <Heatmap buckets={overview?.heatmap.buckets ?? []} rows={overview?.heatmap.rows ?? []} />
        </PanelStatus>
      </section>

      {/* 4. 분야별 트렌드 속도 현황 (섹터 카드) */}
      <div>
        <h2 className="text-lg font-bold text-slate-800 dark:text-slate-100">분야별 트렌드 속도 현황</h2>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">섹터별 실시간 트렌드 점수와 모멘텀입니다.</p>
      </div>
      <PanelStatus isLoading={isLoading} isError={isError} isEmpty={sectorCards.length === 0} label="섹터 트렌드">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {sectorCards.map((sector) => {
            const pending = insufficientSlugs.has(sector.slug);
            return (
              <div
                key={sector.slug}
                className={`p-4 border rounded-xl ${
                  pending
                    ? "border-slate-200 bg-slate-100/60 dark:border-slate-700 dark:bg-slate-800/40"
                    : "border-slate-100 bg-slate-50/50 dark:border-slate-700 dark:bg-slate-900/50"
                }`}
              >
                <div className="flex justify-between items-center mb-2">
                  <span className="font-semibold text-slate-700 dark:text-slate-200">{sector.title}</span>
                  {pending ? (
                    <DataPendingBadge />
                  ) : (
                    <span className="text-xs px-2 py-1 rounded-full bg-indigo-100 text-indigo-600 dark:bg-indigo-900/40 dark:text-indigo-300">
                      {sector.status}
                    </span>
                  )}
                </div>
                <div className={`flex items-end justify-between mb-2 ${pending ? "opacity-40" : ""}`}>
                  <span className="text-2xl font-bold text-slate-900 dark:text-slate-100">{sector.score}</span>
                  {sector.momentum != null && (
                    <span
                      className={`text-xs font-semibold ${sector.momentum < 0 ? "text-rose-600" : "text-emerald-600"}`}
                    >
                      {sector.momentum > 0 ? "+" : ""}
                      {sector.momentum}%
                    </span>
                  )}
                </div>
                <div
                  className={`w-full bg-slate-200 h-2 rounded-full overflow-hidden dark:bg-slate-700 ${
                    pending ? "opacity-40" : ""
                  }`}
                >
                  <div
                    className="h-full bg-indigo-500"
                    style={{ width: `${sector.score}%`, ...(sector.accent ? { backgroundColor: sector.accent } : {}) }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </PanelStatus>
    </div>
  );
}
