"use client";

/**
 * 실시간 펄스(Pulse) 탭 — 섹터 카드 + 속도계·모멘텀·히트맵·점유율(Pulse Gold 즉석 집계).
 */

import {
  useBriefing,
  useCausalChains,
  useCrossover,
  usePulse,
  usePulseOverview,
  useTrendingKeywords,
} from "@/hooks/useDashboard";
import type { Crossover, PulseHeatmapRow, PulseMomentumPoint } from "@/lib/api/dashboard";
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

function CrossoverChart({ data }: { data: Crossover }) {
  const pts = data.series.filter((s) => s.legacy_value !== null && s.emerging_value !== null);
  if (pts.length < 2) {
    return <p className="text-sm text-slate-400">크로스오버 데이터가 아직 부족합니다.</p>;
  }
  const w = 560;
  const h = 180;
  const all = pts.flatMap((p) => [p.legacy_value as number, p.emerging_value as number]);
  const max = Math.max(...all, 1);
  const min = Math.min(...all, 0);
  const span = max - min || 1;
  const xAt = (i: number) => (i / (pts.length - 1)) * w;
  const yAt = (v: number) => h - ((v - min) / span) * h;
  const path = (key: "legacy_value" | "emerging_value") =>
    pts.map((p, i) => `${i === 0 ? "M" : "L"}${xAt(i)},${yAt(p[key] as number)}`).join(" ");
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-44" role="img" aria-label="세대교체 크로스오버 차트">
      <path d={path("legacy_value")} fill="none" stroke="#94a3b8" strokeWidth="2" />
      <path d={path("emerging_value")} fill="none" stroke="#6366f1" strokeWidth="2" />
      {pts.map((p, i) =>
        p.is_crossover ? (
          <circle key={p.bucket} cx={xAt(i)} cy={yAt(p.emerging_value as number)} r="5" fill="#8b5cf6" />
        ) : null,
      )}
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
  const { data: keywords, isLoading: kwLoading, isError: kwError } = useTrendingKeywords();
  const { data: briefing, isLoading: brLoading, isError: brError } = useBriefing();
  const { data: crossover, isLoading: coLoading, isError: coError } = useCrossover();
  const { data: causal, isLoading: ccLoading, isError: ccError } = useCausalChains();

  const sectorCards = (livePulse ?? []).map((s) => ({
    slug: s.sector_slug,
    title: s.sector_name,
    status: s.status_badge,
    score: s.score,
    momentum: s.momentum_pct,
    accent: s.accent_color as string | null,
  }));

  const g = overview?.gauge;
  const cloudMax = Math.max(...(keywords?.cloud ?? []).map((c) => c.weight), 1);
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

      {/* 1.5 오늘의 경제 브리핑 (3줄) */}
      <section className="rounded-2xl border border-slate-200 dark:border-slate-700 p-6">
        <h2 className="text-base font-bold text-slate-800 dark:text-slate-100 mb-3">오늘의 경제 브리핑</h2>
        <PanelStatus
          isLoading={brLoading}
          isError={brError}
          isEmpty={(briefing?.briefings.length ?? 0) === 0}
          label="브리핑"
        >
          <ul className="flex flex-col gap-2">
            {(briefing?.briefings ?? []).map((b) => (
              <li key={b.line_number} className="flex items-start gap-2 text-sm text-slate-700 dark:text-slate-200">
                <span
                  className={`mt-0.5 font-bold ${
                    b.trend_icon === "UP_RIGHT"
                      ? "text-emerald-600"
                      : b.trend_icon === "DOWN_RIGHT"
                        ? "text-rose-600"
                        : "text-slate-400"
                  }`}
                >
                  {b.trend_icon === "UP_RIGHT" ? "↗" : b.trend_icon === "DOWN_RIGHT" ? "↘" : "〰"}
                </span>
                <span>{b.content}</span>
              </li>
            ))}
          </ul>
        </PanelStatus>
      </section>

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

      {/* 2.5 트렌딩 키워드 — 상승 티커 + 빈도 클라우드 */}
      <section className="rounded-2xl border border-slate-200 dark:border-slate-700 p-6">
        <h2 className="text-base font-bold text-slate-800 dark:text-slate-100 mb-4">트렌딩 키워드</h2>
        <PanelStatus
          isLoading={kwLoading}
          isError={kwError}
          isEmpty={(keywords?.cloud.length ?? 0) === 0 && (keywords?.ticker.length ?? 0) === 0}
          label="트렌딩 키워드"
        >
          <div className="flex flex-col gap-5">
            {(keywords?.ticker.length ?? 0) > 0 && (
              <div className="flex flex-wrap gap-2">
                {(keywords?.ticker ?? []).map((t) => (
                  <span
                    key={t.keyword}
                    className="inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-200"
                  >
                    <span className="font-medium">{t.keyword}</span>
                    <span
                      className={`font-semibold ${
                        t.delta_pct === null ? "text-indigo-500" : "text-emerald-600"
                      }`}
                    >
                      {t.value_label}
                    </span>
                  </span>
                ))}
              </div>
            )}
            {(keywords?.cloud.length ?? 0) > 0 && (
              <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                {(keywords?.cloud ?? []).map((c) => (
                  <span
                    key={c.keyword}
                    className="text-slate-600 dark:text-slate-300 leading-tight"
                    style={{ fontSize: `${0.8 + (c.weight / cloudMax) * 1.0}rem` }}
                    title={`${c.weight}회`}
                  >
                    {c.keyword}
                  </span>
                ))}
              </div>
            )}
          </div>
        </PanelStatus>
      </section>

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

      {/* 3.5 세대교체 · 크로스오버 */}
      <section className="rounded-2xl border border-slate-200 dark:border-slate-700 p-6">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-base font-bold text-slate-800 dark:text-slate-100">세대교체 · 크로스오버</h2>
          <div className="flex gap-3 text-xs text-slate-500 dark:text-slate-400">
            <span className="flex items-center gap-1">
              <span className="inline-block w-3 h-0.5 bg-slate-400" />
              {crossover?.legacy_label ?? "전통"}
            </span>
            <span className="flex items-center gap-1">
              <span className="inline-block w-3 h-0.5 bg-indigo-500" />
              {crossover?.emerging_label ?? "신흥"}
            </span>
          </div>
        </div>
        <PanelStatus
          isLoading={coLoading}
          isError={coError}
          isEmpty={(crossover?.series.length ?? 0) === 0}
          label="크로스오버"
        >
          <CrossoverChart
            data={crossover ?? { legacy_label: "전통", emerging_label: "신흥", series: [] }}
          />
        </PanelStatus>
      </section>

      {/* 3.7 인과관계 체인 */}
      <section className="rounded-2xl border border-slate-200 dark:border-slate-700 p-6">
        <h2 className="text-base font-bold text-slate-800 dark:text-slate-100 mb-4">인과관계 체인</h2>
        <PanelStatus
          isLoading={ccLoading}
          isError={ccError}
          isEmpty={(causal?.length ?? 0) === 0}
          label="인과사슬"
        >
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {(causal ?? []).slice(0, 6).map((c) => (
              <div
                key={c.sector_slug}
                className="rounded-xl border border-slate-200 dark:border-slate-700 p-3 flex flex-col gap-1.5"
              >
                <span className="text-xs font-semibold" style={{ color: c.accent_color }}>
                  {c.sector_name}
                </span>
                <div className="rounded-lg bg-slate-50 dark:bg-slate-800 p-2">
                  <p className="text-[10px] text-slate-400">거시 이벤트</p>
                  <p className="text-xs text-slate-700 dark:text-slate-200">{c.macro_event}</p>
                </div>
                <div className="text-center text-slate-300 text-xs leading-none">↓</div>
                <div className="rounded-lg bg-indigo-50 dark:bg-indigo-900/20 p-2">
                  <p className="text-[10px] text-indigo-400">산업 영향</p>
                  <p className="text-xs text-indigo-900 dark:text-indigo-200">{c.industry_impact}</p>
                </div>
                <div className="text-center text-slate-300 text-xs leading-none">↓</div>
                <div className="rounded-lg bg-emerald-50 dark:bg-emerald-900/20 p-2">
                  <p className="text-[10px] text-emerald-500">청년 기회</p>
                  <p className="text-xs text-emerald-900 dark:text-emerald-200">{c.youth_chance}</p>
                </div>
              </div>
            ))}
          </div>
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
