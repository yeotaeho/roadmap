// Pulse 재사용 시각 프리미티브 — 스파크라인·트렌드 상태 배지

"use client";

import { Flame, Minus, TrendingDown } from "lucide-react";

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
