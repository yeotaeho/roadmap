// 상담실 우측 — 자기모델(RIASEC 레이더·주요유형·서사·근거·성격 placeholder) 실데이터 패널
"use client";

import { useQuery } from "@tanstack/react-query";
import { Radar as RadarIcon, Sparkles } from "lucide-react";
import {
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
} from "recharts";
import { fetchSelfModel, type SelfModelLive } from "@/lib/api/selfModel";
import { useStore } from "@/store";

const INDIGO = "#4F46E5";
const RIASEC_LABEL: Record<string, string> = {
  R: "현실", I: "탐구", A: "예술", S: "사회", E: "진취", C: "관습",
};
const RIASEC_TYPE: Record<string, string> = {
  R: "현실형", I: "탐구형", A: "예술형", S: "사회형", E: "진취형", C: "관습형",
};
const POSITIVE_DIMS = new Set(["like", "value", "aspiration", "skill_signal"]);

export function SelfModelPanel() {
  const profile = useStore((s) => s.profile);
  const authed = !!profile?.id;
  const { data, isLoading, isError } = useQuery<SelfModelLive>({
    queryKey: ["self-model"],
    queryFn: fetchSelfModel,
    staleTime: 5 * 60 * 1000,
    enabled: authed,
  });

  const riasec = data?.riasec ?? null;
  const radarRows = riasec
    ? (["R", "I", "A", "S", "E", "C"] as const).map((c) => ({
        axis: RIASEC_LABEL[c],
        value: riasec.scores[c] ?? 50,
      }))
    : [];
  const topCodes = riasec?.top_codes ?? [];
  const positives = (data?.evidence ?? [])
    .filter((e) => POSITIVE_DIMS.has(e.dimension))
    .slice(0, 8);
  const hasAny = !!riasec || !!data?.narrativeSummary || (data?.evidence?.length ?? 0) > 0;

  return (
    <div className="flex min-h-0 flex-col gap-3 overflow-y-auto rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-800">
      <div className="flex items-center gap-2 text-sm font-semibold text-slate-800 dark:text-slate-100">
        <RadarIcon className="h-4 w-4 text-indigo-600" aria-hidden />
        나의 성향 지도
      </div>

      {!authed ? (
        <p className="py-8 text-center text-xs leading-relaxed text-slate-500 dark:text-slate-400">
          상담을 나누면 여기에 나의 성향이 나타나요.
        </p>
      ) : isLoading ? (
        <p className="py-8 text-center text-xs text-slate-400 dark:text-slate-500">불러오는 중…</p>
      ) : isError ? (
        <p className="py-8 text-center text-xs text-slate-400 dark:text-slate-500">잠시 후 다시 시도해 주세요.</p>
      ) : !hasAny ? (
        <p className="py-8 text-center text-xs leading-relaxed text-slate-500 dark:text-slate-400">
          상담을 나누면 여기에 나의 성향이 나타나요.
        </p>
      ) : (
        <>
          {riasec && (
            <div className="h-[220px] w-full min-w-0">
              <ResponsiveContainer width="100%" height={220}>
                <RadarChart cx="50%" cy="50%" outerRadius="72%" data={radarRows}>
                  <PolarGrid stroke="#e2e8f0" />
                  <PolarAngleAxis dataKey="axis" tick={{ fill: "#64748b", fontSize: 11 }} />
                  <PolarRadiusAxis angle={30} domain={[0, 100]} tick={false} axisLine={false} />
                  <Radar dataKey="value" stroke={INDIGO} fill={INDIGO} fillOpacity={0.22} isAnimationActive animationDuration={600} />
                </RadarChart>
              </ResponsiveContainer>
            </div>
          )}

          {topCodes.length > 0 ? (
            <div className="flex flex-wrap gap-1.5">
              {topCodes.map((c) => (
                <span key={c} className="rounded-full bg-indigo-50 px-2.5 py-1 text-[11px] font-semibold text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-300">
                  {RIASEC_TYPE[c] ?? c}
                </span>
              ))}
            </div>
          ) : (
            <p className="text-[11px] text-slate-500 dark:text-slate-400">아직 흥미가 분화 중이에요. 대화가 쌓이면 뚜렷해져요.</p>
          )}

          {data?.narrativeSummary && (
            <p className="rounded-xl bg-slate-50 px-3 py-2 text-xs leading-relaxed text-slate-700 dark:bg-slate-900/50 dark:text-slate-200">
              {data.narrativeSummary}
            </p>
          )}

          {positives.length > 0 && (
            <div>
              <p className="mb-1.5 flex items-center gap-1 text-[11px] font-semibold text-slate-600 dark:text-slate-400">
                <Sparkles className="h-3 w-3 text-amber-500" aria-hidden /> 발견된 근거
              </p>
              <div className="flex flex-wrap gap-1.5">
                {positives.map((e, i) => (
                  <span key={i} className="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[11px] text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300">
                    {e.content}
                  </span>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      <div className="mt-1 rounded-xl border border-dashed border-slate-200 px-3 py-2.5 text-[11px] leading-relaxed text-slate-400 dark:border-slate-700 dark:text-slate-500">
        대화가 쌓이면 성격 5요인(Big Five)도 여기에 나타나요.
      </div>
      <p className="text-center text-[10px] text-slate-400 dark:text-slate-500">나의 성향은 매일 대화를 바탕으로 정리돼요.</p>
    </div>
  );
}
