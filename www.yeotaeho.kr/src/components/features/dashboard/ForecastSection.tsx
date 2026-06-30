"use client";

/** 14일 시장 전망 섹션 — TimesFM 예측 기반 섹터별 선행 지표(전망 점수·방향 배지·수익률·신뢰도). */

import { useForecast } from "@/hooks/useDashboard";
import { PanelStatus } from "./PanelStatus";

// 방향 배지 색조 — 강세/상승 emerald · 중립 slate · 하락/약세 rose.
function badgeTone(badge: string): string {
  if (badge.includes("강세") || badge.includes("상승")) {
    return "bg-emerald-50 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300";
  }
  if (badge.includes("하락") || badge.includes("약세")) {
    return "bg-rose-50 text-rose-700 dark:bg-rose-900/30 dark:text-rose-300";
  }
  return "bg-slate-100 text-slate-500 dark:bg-slate-700 dark:text-slate-300";
}

function confidenceLabel(confidence: number | null): string {
  if (confidence == null) return "—";
  if (confidence >= 0.66) return "높음";
  if (confidence >= 0.33) return "보통";
  return "낮음";
}

export function ForecastSection() {
  const { data, isLoading, isError } = useForecast();
  const cards = data ?? [];

  return (
    <>
      <div>
        <h2 className="text-lg font-bold text-slate-800 dark:text-slate-100">14일 시장 전망</h2>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          AI 예측 기반 선행 지표 — 향후 14일 섹터별 자금 흐름 추세입니다.
        </p>
      </div>
      <PanelStatus isLoading={isLoading} isError={isError} isEmpty={cards.length === 0} label="시장 전망">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {cards.map((s) => {
            const ret = s.predicted_return_pct;
            const conf = s.confidence ?? 0;
            return (
              <div
                key={s.sector_slug}
                className="p-4 border rounded-xl border-slate-100 bg-slate-50/50 dark:border-slate-700 dark:bg-slate-900/50"
              >
                <div className="flex justify-between items-center mb-1.5 gap-2">
                  <span className="font-semibold text-slate-700 dark:text-slate-200 truncate">{s.sector_name}</span>
                  <span
                    className={`shrink-0 text-[11px] font-semibold px-2 py-0.5 rounded-full whitespace-nowrap ${badgeTone(
                      s.direction_badge,
                    )}`}
                  >
                    {s.direction_badge}
                  </span>
                </div>
                <div className="flex items-end gap-2 mb-2">
                  <span className="text-2xl font-bold text-slate-900 dark:text-slate-100">{s.score}</span>
                  {ret != null && (
                    <span
                      className={`mb-1 text-xs font-semibold ${ret < 0 ? "text-rose-600" : "text-emerald-600"}`}
                    >
                      {ret > 0 ? "+" : ""}
                      {ret.toFixed(1)}%
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <div className="flex-1 bg-slate-200 dark:bg-slate-700 h-1.5 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-indigo-400"
                      style={{ width: `${Math.round(conf * 100)}%` }}
                    />
                  </div>
                  <span className="text-[10px] text-slate-400 shrink-0 whitespace-nowrap">
                    신뢰도 {confidenceLabel(s.confidence)}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </PanelStatus>
    </>
  );
}
