"use client";

/**
 * 실시간 펄스(Pulse) 탭 — 섹터별 트렌드 점수(Pulse Gold) 라이브 서빙.
 */

import { usePulse } from "@/hooks/useDashboard";
import { PanelStatus } from "./PanelStatus";

export function PulseTab() {
  const { data: livePulse, isLoading, isError } = usePulse();
  const sectorCards = (livePulse ?? []).map((s) => ({
    slug: s.sector_slug,
    title: s.sector_name,
    status: s.status_badge,
    score: s.score,
    momentum: s.momentum_pct,
    accent: s.accent_color as string | null,
  }));

  return (
    <div className="w-full flex flex-col gap-6 font-sans">
      <div>
        <h2 className="text-lg font-bold text-slate-800 dark:text-slate-100">분야별 트렌드 속도 현황</h2>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          섹터별 실시간 트렌드 점수와 모멘텀입니다.
        </p>
      </div>

      <PanelStatus
        isLoading={isLoading}
        isError={isError}
        isEmpty={sectorCards.length === 0}
        label="섹터 트렌드"
      >
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {sectorCards.map((sector) => (
            <div
              key={sector.slug}
              className="p-4 border border-slate-100 rounded-xl bg-slate-50/50 dark:border-slate-700 dark:bg-slate-900/50"
            >
              <div className="flex justify-between items-center mb-2">
                <span className="font-semibold text-slate-700 dark:text-slate-200">{sector.title}</span>
                <span className="text-xs px-2 py-1 rounded-full bg-indigo-100 text-indigo-600 dark:bg-indigo-900/40 dark:text-indigo-300">
                  {sector.status}
                </span>
              </div>
              <div className="flex items-end justify-between mb-2">
                <span className="text-2xl font-bold text-slate-900 dark:text-slate-100">{sector.score}</span>
                {sector.momentum != null && (
                  <span
                    className={`text-xs font-semibold ${
                      sector.momentum < 0 ? "text-rose-600" : "text-emerald-600"
                    }`}
                  >
                    {sector.momentum > 0 ? "+" : ""}
                    {sector.momentum}%
                  </span>
                )}
              </div>
              <div className="w-full bg-slate-200 h-2 rounded-full overflow-hidden dark:bg-slate-700">
                <div
                  className="h-full bg-indigo-500"
                  style={{
                    width: `${sector.score}%`,
                    ...(sector.accent ? { backgroundColor: sector.accent } : {}),
                  }}
                />
              </div>
            </div>
          ))}
        </div>
      </PanelStatus>
    </div>
  );
}
