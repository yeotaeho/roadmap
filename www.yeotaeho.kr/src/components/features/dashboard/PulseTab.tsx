"use client";

/**
 * 실시간 펄스(Pulse) 탭 — 히어로(모멘텀 리더) + 섹터 카드 + 점진적 공개(모멘텀·히트맵·점유율·크로스오버·키워드).
 */

import { useMemo, useState, type ReactNode } from "react";
import { Crown, X } from "lucide-react";
import {
  useBriefing,
  useCausalChains,
  useCrossover,
  usePulse,
  usePulseHistory,
  usePulseOverview,
  useTrendingKeywords,
} from "@/hooks/useDashboard";
import type {
  Crossover,
  PulseHeatmapRow,
  PulseHistoryPoint,
  PulseMomentumPoint,
} from "@/lib/api/dashboard";
import { PanelStatus } from "./PanelStatus";
import { ForecastSection } from "./ForecastSection";
import { CausalFlow, Sparkline, TrendStatusBadge } from "./PulseViz";

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

// LNB에서 선택 가능한 펄스 세부 섹션 식별자. DashboardView와 공유.
export type PulseSectionId =
  | "overview"
  | "forecast"
  | "causal"
  | "momentum"
  | "share"
  | "heatmap"
  | "crossover"
  | "keywords";

// 선택된 세부 섹션 공통 래퍼 — 제목 헤딩 + 카드 테두리.
function SectionCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-2xl border border-slate-200 dark:border-slate-700 p-6">
      <h2 className="text-base font-bold text-slate-800 dark:text-slate-100 mb-4">{title}</h2>
      {children}
    </section>
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

// 일별 히스토리 포인트를 주(월요일 시작) 단위 평균 점수로 묶는다.
function toWeeklyPoints(
  points: PulseHistoryPoint[],
): { key: string; label: string; value: number }[] {
  const byWeek = new Map<string, { label: string; sum: number; n: number }>();
  for (const p of points) {
    const d = new Date(`${p.recorded_date}T00:00:00`);
    const monday = new Date(d);
    monday.setDate(d.getDate() - ((d.getDay() + 6) % 7));
    const key = `${monday.getFullYear()}-${String(monday.getMonth() + 1).padStart(2, "0")}-${String(
      monday.getDate(),
    ).padStart(2, "0")}`;
    const cur = byWeek.get(key) ?? {
      label: `${monday.getMonth() + 1}.${monday.getDate()}`,
      sum: 0,
      n: 0,
    };
    cur.sum += p.score;
    cur.n += 1;
    byWeek.set(key, cur);
  }
  return [...byWeek.entries()]
    .sort(([a], [b]) => (a < b ? -1 : 1))
    .map(([key, v]) => ({ key, label: v.label, value: Math.round(v.sum / v.n) }));
}

// 주간 트렌드 라인 차트 — 격자·포인트·주차 라벨·마지막 값 배지.
function WeeklyTrendChart({
  points,
  accent,
}: {
  points: { key: string; label: string; value: number }[];
  accent?: string | null;
}) {
  if (points.length < 2) {
    return <p className="text-sm text-slate-400">주간 추이를 그리기엔 데이터가 아직 부족합니다.</p>;
  }
  const w = 560;
  const h = 210;
  const padL = 34;
  const padR = 30;
  const padT = 28;
  const padB = 26;
  const values = points.map((p) => p.value);
  const max = Math.max(...values);
  const min = Math.min(...values);
  const span = max - min || 1;
  const xAt = (i: number) => padL + (i / (points.length - 1)) * (w - padL - padR);
  const yAt = (v: number) => padT + (1 - (v - min) / span) * (h - padT - padB);
  const color = accent ?? "#6366f1";
  const line = points.map((p, i) => `${i === 0 ? "M" : "L"}${xAt(i).toFixed(1)},${yAt(p.value).toFixed(1)}`).join(" ");
  const gridRows = [0, 0.5, 1].map((t) => ({ y: padT + t * (h - padT - padB), v: Math.round(max - t * span) }));
  const labelStep = Math.max(1, Math.ceil(points.length / 8));
  const last = points[points.length - 1];
  const lastX = xAt(points.length - 1);
  const lastY = yAt(last.value);
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-56" role="img" aria-label="주간 트렌드 차트">
      {gridRows.map((g) => (
        <g key={g.y}>
          <line x1={padL} y1={g.y} x2={w - padR} y2={g.y} stroke="currentColor" strokeDasharray="3 4" className="text-slate-200 dark:text-slate-700" />
          <text x={padL - 6} y={g.y + 3} textAnchor="end" fontSize="9" className="fill-slate-400">
            {g.v}
          </text>
        </g>
      ))}
      <path
        d={`${line} L${lastX.toFixed(1)},${h - padB} L${xAt(0).toFixed(1)},${h - padB} Z`}
        fill={color}
        fillOpacity="0.1"
      />
      <path d={line} fill="none" stroke={color} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
      {points.map((p, i) => (
        <g key={p.key}>
          <circle cx={xAt(i)} cy={yAt(p.value)} r="3" fill={color} stroke="white" strokeWidth="1.5">
            <title>{`${p.label} 주 · ${p.value}점`}</title>
          </circle>
          {i % labelStep === 0 && (
            <text x={xAt(i)} y={h - padB + 14} textAnchor="middle" fontSize="9" className="fill-slate-400">
              {p.label}
            </text>
          )}
        </g>
      ))}
      <g>
        <rect x={lastX - 16} y={lastY - 24} width="32" height="16" rx="8" fill={color} />
        <text x={lastX} y={lastY - 13} textAnchor="middle" fontSize="9" fontWeight="bold" fill="white">
          {last.value}
        </text>
      </g>
    </svg>
  );
}

// 선택된 섹터의 주간 트렌드 드릴다운 패널 — /pulse/{sector}/history 를 주 단위로 집계해 그린다.
function SectorHistoryPanel({
  slug,
  accent,
  onClose,
}: {
  slug: string;
  accent?: string | null;
  onClose: () => void;
}) {
  const { data, isLoading, isError } = usePulseHistory(slug);
  const weekly = useMemo(() => toWeeklyPoints(data?.points ?? []), [data]);
  return (
    <section className="rounded-2xl border border-indigo-200 dark:border-indigo-900/50 bg-white dark:bg-slate-900 p-6">
      <div className="flex items-start justify-between gap-3 mb-4">
        <div>
          <h3 className="text-base font-bold text-slate-800 dark:text-slate-100">
            {data?.sector_name ?? "섹터"} 주간 트렌드
          </h3>
          <p className="mt-0.5 text-xs text-slate-400">
            최근 {weekly.length}주 · 주 평균 트렌드 점수
          </p>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="주간 트렌드 닫기"
          className="p-1 rounded-md text-slate-400 hover:text-slate-600 hover:bg-slate-100 dark:hover:text-slate-200 dark:hover:bg-slate-800"
        >
          <X className="w-4 h-4" aria-hidden />
        </button>
      </div>
      <PanelStatus isLoading={isLoading} isError={isError} isEmpty={weekly.length === 0} label="주간 트렌드">
        <WeeklyTrendChart points={weekly} accent={accent} />
      </PanelStatus>
    </section>
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

export function PulseTab({ section = "overview" }: { section?: PulseSectionId }) {
  const { data: livePulse, isLoading, isError } = usePulse();
  const { data: overview, isLoading: ovLoading, isError: ovError } = usePulseOverview();
  const { data: keywords, isLoading: kwLoading, isError: kwError } = useTrendingKeywords();
  const { data: briefing, isLoading: brLoading, isError: brError } = useBriefing();
  const { data: crossover, isLoading: coLoading, isError: coError } = useCrossover();
  const { data: causal, isLoading: ccLoading, isError: ccError } = useCausalChains();

  // 클릭한 섹터 카드 — 주간 트렌드 드릴다운 대상. 같은 카드 재클릭 시 닫힘.
  const [selectedSlug, setSelectedSlug] = useState<string | null>(null);

  const sectorCards = (livePulse ?? []).map((s) => ({
    slug: s.sector_slug,
    title: s.sector_name,
    score: s.score,
    momentum: s.momentum_pct,
    accent: s.accent_color as string | null,
  }));

  const g = overview?.gauge;
  const cloudMax = Math.max(...(keywords?.cloud ?? []).map((c) => c.weight), 1);

  // 섹터별 시간축 점수(히트맵 셀) → 스파크라인 입력. 인과사슬 industry_impact → 카드 드라이버 한 줄.
  const sparkBySlug = new Map(
    (overview?.heatmap.rows ?? []).map((r) => [
      r.sector_slug,
      r.cells.map((c) => c.score).filter((s): s is number => s != null),
    ]),
  );
  const causalBySlug = new Map((causal ?? []).map((c) => [c.sector_slug, c]));
  const insufficientSlugs = new Set(
    (overview?.heatmap.rows ?? [])
      .filter((r) => r.data_status === "insufficient")
      .map((r) => r.sector_slug),
  );

  const mover = g?.top_mover ?? null;
  const moverSpark = mover ? sparkBySlug.get(mover.sector_slug) ?? [] : [];
  const moverFallbackSpark = (overview?.momentum_series ?? []).map((p) => p.value);
  const moverChance = mover ? causalBySlug.get(mover.sector_slug)?.youth_chance : undefined;

  return (
    <div className="w-full flex flex-col gap-6 font-sans">
      {section === "overview" && (
        <>
      {/* 1. 히어로 — 오늘의 모멘텀 리더 */}
      <PanelStatus isLoading={ovLoading} isError={ovError} isEmpty={!g} label="모멘텀 리더">
        <div className="rounded-2xl border border-indigo-200 dark:border-indigo-900/50 bg-white dark:bg-slate-900 p-5 sm:p-6">
          <div className="flex items-center justify-between mb-3">
            <span className="inline-flex items-center gap-1.5 text-sm font-medium text-slate-500 dark:text-slate-400">
              <Crown className="w-4 h-4 text-indigo-600" aria-hidden /> 오늘의 모멘텀 리더
            </span>
            <span className="text-xs text-slate-400">
              속도 {g?.speed_kmh ?? "—"}km/h · 주간 {g?.weekly_index ?? "—"}/100
            </span>
          </div>
          {mover ? (
            <div className="flex items-start gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2.5 flex-wrap">
                  <span className="text-2xl font-bold text-slate-900 dark:text-slate-100">
                    {mover.sector_name}
                  </span>
                  <TrendStatusBadge momentum={mover.momentum_pct} />
                  <span className="text-sm font-bold text-emerald-600">
                    {mover.momentum_pct > 0 ? "+" : ""}
                    {mover.momentum_pct}%
                  </span>
                </div>
                <p className="mt-3 text-sm text-slate-600 dark:text-slate-300 leading-relaxed border-l-2 border-indigo-500 pl-3">
                  지금 가장 빠르게 움직이는 분야예요.
                  {moverChance ? ` ${moverChance}` : ""}
                </p>
              </div>
              <Sparkline
                values={moverSpark.length >= 2 ? moverSpark : moverFallbackSpark}
                width={120}
                height={36}
                className="w-28 h-9 shrink-0"
              />
            </div>
          ) : (
            <p className="text-sm text-slate-400">모멘텀 신호가 아직 없습니다.</p>
          )}
        </div>
      </PanelStatus>

      {/* 2. 오늘의 경제 브리핑 (3줄) */}
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

      {/* 3. 분야별 트렌드 — 밀도 높인 섹터 카드(상태 배지 + 드라이버 + 스파크라인) */}
      <div>
        <h2 className="text-lg font-bold text-slate-800 dark:text-slate-100">분야별 트렌드 속도 현황</h2>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">섹터별 실시간 트렌드 점수와 모멘텀입니다.</p>
      </div>
      <PanelStatus isLoading={isLoading} isError={isError} isEmpty={sectorCards.length === 0} label="섹터 트렌드">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {sectorCards.map((sector) => {
            const pending = insufficientSlugs.has(sector.slug);
            const spark = sparkBySlug.get(sector.slug) ?? [];
            const driver = causalBySlug.get(sector.slug)?.industry_impact;
            const selected = selectedSlug === sector.slug;
            return (
              <button
                type="button"
                key={sector.slug}
                onClick={() => setSelectedSlug((cur) => (cur === sector.slug ? null : sector.slug))}
                aria-expanded={selected}
                className={`p-4 border rounded-xl text-left cursor-pointer transition-colors hover:border-indigo-300 dark:hover:border-indigo-700 ${
                  selected ? "ring-2 ring-indigo-500 " : ""
                }${
                  pending
                    ? "border-slate-200 bg-slate-100/60 dark:border-slate-700 dark:bg-slate-800/40"
                    : "border-slate-100 bg-slate-50/50 dark:border-slate-700 dark:bg-slate-900/50"
                }`}
              >
                <div className="flex justify-between items-center mb-1.5">
                  <span className="font-semibold text-slate-700 dark:text-slate-200">{sector.title}</span>
                  {pending ? <DataPendingBadge /> : <TrendStatusBadge momentum={sector.momentum} />}
                </div>
                <div className={`flex items-end gap-2 mb-1 ${pending ? "opacity-40" : ""}`}>
                  <span className="text-2xl font-bold text-slate-900 dark:text-slate-100">{sector.score}</span>
                  {sector.momentum != null && (
                    <span
                      className={`mb-1 text-xs font-semibold ${sector.momentum < 0 ? "text-rose-600" : "text-emerald-600"}`}
                    >
                      {sector.momentum > 0 ? "+" : ""}
                      {sector.momentum}%
                    </span>
                  )}
                </div>
                {driver && !pending && (
                  <p className="mb-2 text-xs text-slate-500 dark:text-slate-400 leading-snug line-clamp-2">{driver}</p>
                )}
                {spark.length >= 2 ? (
                  <Sparkline values={spark} className={`w-full h-6 ${pending ? "opacity-40" : ""}`} />
                ) : (
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
                )}
              </button>
            );
          })}
        </div>
      </PanelStatus>

      {/* 3.1 선택 섹터 주간 트렌드 드릴다운 */}
      {selectedSlug && (
        <SectorHistoryPanel
          slug={selectedSlug}
          accent={sectorCards.find((s) => s.slug === selectedSlug)?.accent ?? null}
          onClose={() => setSelectedSlug(null)}
        />
      )}
        </>
      )}

      {/* 3.5 14일 시장 전망 — 현재 트렌드의 미래(선행 지표) */}
      {section === "forecast" && <ForecastSection />}

      {/* 4. 인과관계 체인 — 거시에서 나의 기회까지 */}
      {section === "causal" && (
      <SectionCard title="인과관계 체인">
        <PanelStatus
          isLoading={ccLoading}
          isError={ccError}
          isEmpty={(causal?.length ?? 0) === 0}
          label="인과사슬"
        >
          <div className="flex flex-col gap-3">
            {(causal ?? []).slice(0, 4).map((c) => (
              <CausalFlow
                key={c.sector_slug}
                sectorName={c.sector_name}
                accentColor={c.accent_color}
                macro={c.macro_event}
                industry={c.industry_impact}
                chance={c.youth_chance}
              />
            ))}
          </div>
        </PanelStatus>
      </SectionCard>
      )}

      {/* 5. 세부 섹션 — LNB에서 선택 */}
      {section === "momentum" && (
      <SectionCard title="연간 모멘텀 트렌드">
        <PanelStatus
          isLoading={ovLoading}
          isError={ovError}
          isEmpty={(overview?.momentum_series.length ?? 0) === 0}
          label="모멘텀"
        >
          <MomentumChart points={overview?.momentum_series ?? []} />
        </PanelStatus>
      </SectionCard>
      )}

      {section === "share" && (
      <SectionCard title="관심 점유율">
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
      </SectionCard>
      )}

      {section === "heatmap" && (
      <SectionCard title="Top 섹터 히트맵 (분야 × 시간)">
        <PanelStatus
          isLoading={ovLoading}
          isError={ovError}
          isEmpty={(overview?.heatmap.rows.length ?? 0) === 0}
          label="히트맵"
        >
          <Heatmap buckets={overview?.heatmap.buckets ?? []} rows={overview?.heatmap.rows ?? []} />
        </PanelStatus>
      </SectionCard>
      )}

      {section === "crossover" && (
      <SectionCard title="세대교체 · 크로스오버">
        <div className="mb-3 flex gap-3 text-xs text-slate-500 dark:text-slate-400">
          <span className="flex items-center gap-1">
            <span className="inline-block w-3 h-0.5 bg-slate-400" />
            {crossover?.legacy_label ?? "전통"}
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block w-3 h-0.5 bg-indigo-500" />
            {crossover?.emerging_label ?? "신흥"}
          </span>
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
      </SectionCard>
      )}

      {section === "keywords" && (
      <SectionCard title="트렌딩 키워드">
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
      </SectionCard>
      )}
    </div>
  );
}
