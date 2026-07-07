// 섹터 주간 트렌드 공용 프리미티브 — 일별 히스토리의 주 단위 집계와 라인 차트

"use client";

import type { PulseHistoryPoint } from "@/lib/api/dashboard";

// 일별 히스토리 포인트를 주(월요일 시작) 단위 평균 점수로 묶는다.
export function toWeeklyPoints(
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
export function WeeklyTrendChart({
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
