// Pulse 재사용 시각 프리미티브 — 스파크라인·트렌드 상태 배지·크로스오버 차트

"use client";

import { ArrowRight, Flame, Minus, TrendingDown } from "lucide-react";
import type { Crossover } from "@/lib/api/dashboard";

// 시간축 점수 배열을 미니 추이 선으로. 추세 방향에 따라 색이 바뀐다.
export function Sparkline({
  values,
  width = 100,
  height = 24,
  className,
}: {
  values: number[];
  width?: number;
  height?: number;
  className?: string;
}) {
  const pts = values.filter((v): v is number => v != null && !Number.isNaN(v));
  if (pts.length < 2) return null;

  const max = Math.max(...pts);
  const min = Math.min(...pts);
  const span = max - min || 1;
  const pad = 2;
  const xAt = (i: number) => (i / (pts.length - 1)) * width;
  const yAt = (v: number) => height - pad - ((v - min) / span) * (height - pad * 2);

  const trend = pts[pts.length - 1] - pts[0];
  const stroke = trend > 1 ? "#10b981" : trend < -1 ? "#f43f5e" : "#94a3b8";
  const line = pts
    .map((v, i) => `${i === 0 ? "M" : "L"}${xAt(i).toFixed(1)},${yAt(v).toFixed(1)}`)
    .join(" ");

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className={className}
      preserveAspectRatio="none"
      role="img"
      aria-label="추이 스파크라인"
    >
      <path d={line} fill="none" stroke={stroke} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

// 세대교체 크로스오버 차트 — 전통 vs 신흥 그룹 월 평균 score 시계열·교차점.
export function CrossoverChart({ data }: { data: Crossover }) {
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

export type TrendStatus = "surge" | "steady" | "decline";

// 모멘텀(%)을 급등/안정/하락 3단계로 분류. 임계값은 휴리스틱(추후 데이터로 튜닝).
export function classifyTrend(momentum: number | null | undefined): TrendStatus | null {
  if (momentum == null) return null;
  if (momentum >= 8) return "surge";
  if (momentum <= -5) return "decline";
  return "steady";
}

const STATUS_META: Record<
  TrendStatus,
  { label: string; cls: string; Icon: typeof Flame }
> = {
  surge: {
    label: "급등",
    cls: "text-emerald-700 bg-emerald-50 dark:text-emerald-300 dark:bg-emerald-900/30",
    Icon: Flame,
  },
  steady: {
    label: "안정",
    cls: "text-slate-600 bg-slate-100 dark:text-slate-300 dark:bg-slate-700/60",
    Icon: Minus,
  },
  decline: {
    label: "하락",
    cls: "text-rose-700 bg-rose-50 dark:text-rose-300 dark:bg-rose-900/30",
    Icon: TrendingDown,
  },
};

// 트렌드 상태 배지 — 모멘텀이 없으면 렌더하지 않는다(호출부에서 fallback 처리).
export function TrendStatusBadge({ momentum }: { momentum: number | null | undefined }) {
  const status = classifyTrend(momentum);
  if (!status) return null;
  const { label, cls, Icon } = STATUS_META[status];
  return (
    <span
      className={`inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full whitespace-nowrap ${cls}`}
    >
      <Icon className="w-3 h-3" aria-hidden />
      {label}
    </span>
  );
}

function CausalStep({
  label,
  text,
  tone,
}: {
  label: string;
  text: string;
  tone: "slate" | "indigo" | "emerald";
}) {
  const cls = {
    slate: "bg-slate-50 dark:bg-slate-800",
    indigo: "bg-indigo-50 dark:bg-indigo-900/20",
    emerald: "bg-emerald-50 dark:bg-emerald-900/20",
  }[tone];
  const labelCls = {
    slate: "text-slate-400",
    indigo: "text-indigo-400",
    emerald: "text-emerald-500",
  }[tone];
  const textCls = {
    slate: "text-slate-700 dark:text-slate-200",
    indigo: "text-indigo-900 dark:text-indigo-200",
    emerald: "text-emerald-900 dark:text-emerald-200 font-semibold",
  }[tone];
  return (
    <div className={`flex-1 rounded-lg p-2.5 ${cls}`}>
      <p className={`text-[10px] ${labelCls}`}>{label}</p>
      <p className={`mt-1 text-xs leading-snug ${textCls}`}>{text}</p>
    </div>
  );
}

// 인과사슬 가로 플로우 — 거시 → 산업 → 청년 기회. 모바일은 세로, 데스크톱은 가로 화살표.
export function CausalFlow({
  sectorName,
  accentColor,
  macro,
  industry,
  chance,
}: {
  sectorName: string;
  accentColor?: string | null;
  macro: string;
  industry: string;
  chance: string;
}) {
  const arrow = (
    <div className="flex items-center justify-center shrink-0">
      <ArrowRight className="w-4 h-4 text-indigo-500 rotate-90 sm:rotate-0" aria-hidden />
    </div>
  );
  return (
    <div className="rounded-xl border border-slate-200 dark:border-slate-700 p-3">
      <span className="text-xs font-semibold" style={accentColor ? { color: accentColor } : undefined}>
        {sectorName}
      </span>
      <div className="mt-2 flex flex-col sm:flex-row sm:items-stretch gap-1.5">
        <CausalStep label="거시 이벤트" text={macro} tone="slate" />
        {arrow}
        <CausalStep label="산업 영향" text={industry} tone="indigo" />
        {arrow}
        <CausalStep label="청년 기회" text={chance} tone="emerald" />
      </div>
    </div>
  );
}

// 원형 게이지 — 0~100 점수를 링으로. 라벨/추이는 호출부에서 옆에 배치.
export function SyncGauge({ value, size = 64 }: { value: number; size?: number }) {
  const pct = Math.max(0, Math.min(100, value));
  const r = 30;
  const circ = 2 * Math.PI * r;
  const filled = (pct / 100) * circ;
  return (
    <svg viewBox="0 0 72 72" width={size} height={size} className="shrink-0" role="img" aria-label={`싱크 ${Math.round(pct)}%`}>
      <circle cx="36" cy="36" r={r} fill="none" stroke="currentColor" strokeWidth="7" className="text-slate-200 dark:text-slate-700" />
      <circle
        cx="36"
        cy="36"
        r={r}
        fill="none"
        stroke="#4f46e5"
        strokeWidth="7"
        strokeLinecap="round"
        strokeDasharray={`${filled.toFixed(1)} ${circ.toFixed(1)}`}
        transform="rotate(-90 36 36)"
      />
      <text x="36" y="41" textAnchor="middle" fontSize="17" fontWeight="bold" className="fill-slate-900 dark:fill-slate-100">
        {Math.round(pct)}
      </text>
    </svg>
  );
}
