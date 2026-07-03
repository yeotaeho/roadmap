// 상담실 자기모델 편집 모달 — 축당 낮음·중간·높음·AI판단 세그먼트 + 서사
"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { updateSelfModel, type AxisLevel, type SelfModelEdits, type SelfModelLive } from "@/lib/api/selfModel";
import { useStore } from "@/store";

type Seg = AxisLevel | "auto";
const RIASEC = [
  { key: "R", label: "현실형" }, { key: "I", label: "탐구형" }, { key: "A", label: "예술형" },
  { key: "S", label: "사회형" }, { key: "E", label: "진취형" }, { key: "C", label: "관습형" },
] as const;
const BIG_FIVE = [
  { key: "O", label: "개방성" }, { key: "C", label: "성실성" }, { key: "E", label: "외향성" },
  { key: "A", label: "우호성" }, { key: "stability", label: "정서안정성" },
] as const;
const SEGS: { v: Seg; t: string }[] = [
  { v: "low", t: "낮음" }, { v: "mid", t: "중간" }, { v: "high", t: "높음" }, { v: "auto", t: "AI판단" },
];

function scoreToLevel(v: number | undefined): AxisLevel {
  if (typeof v !== "number") return "mid";
  if (v >= 62) return "high";
  if (v <= 38) return "low";
  return "mid";
}

export function SelfModelEditModal({ data, onClose }: { data: SelfModelLive | null; onClose: () => void }) {
  const profile = useStore((s) => s.profile);
  const qc = useQueryClient();
  const riasecUserForm = (data?.axisSource || {}).riasec === "user_form";
  const bigFiveUserForm = (data?.axisSource || {}).big_five === "user_form";

  // 사용자 확정(user_form) 축만 현재 레벨을 프리필. 코치 소유 축은 "AI판단" 기본 —
  // 손대지 않고 저장하면 코치 소유가 유지되고(footgun 방지), 레벨을 고르면 그때 user_form 이 된다.
  const [riasec, setRiasec] = useState<Record<string, Seg>>(() =>
    Object.fromEntries(RIASEC.map((a) => [a.key,
      riasecUserForm ? scoreToLevel(data?.riasec?.scores?.[a.key as keyof typeof data.riasec.scores]) : "auto"])),
  );
  const [bigFive, setBigFive] = useState<Record<string, Seg>>(() =>
    Object.fromEntries(BIG_FIVE.map((a) => {
      const raw = a.key === "stability"
        ? (typeof data?.bigFive?.scores?.N === "number" ? 100 - data.bigFive.scores.N : undefined)
        : data?.bigFive?.scores?.[a.key as keyof typeof data.bigFive.scores];
      return [a.key, bigFiveUserForm ? scoreToLevel(raw) : "auto"];
    })),
  );
  const narrativeUserForm = (data?.axisSource || {}).narrative_summary === "user_form";
  const [narrative, setNarrative] = useState(narrativeUserForm ? (data?.narrativeSummary ?? "") : "");

  // 그룹은 provenance 단위(전체가 user_form 로 동결)라, 부분 편집 시 미터치 축을 현재
  // 코치 추론 레벨로 보존해야 중립(50) 리셋을 막는다. data 클로저에 접근하는 리졸버.
  function resolveLevels(state: Record<string, Seg>, group: "riasec" | "big_five"): Record<string, AxisLevel> {
    const out: Record<string, AxisLevel> = {};
    for (const [k, v] of Object.entries(state)) {
      if (v !== "auto") { out[k] = v; continue; }
      const raw =
        group === "riasec"
          ? data?.riasec?.scores?.[k as keyof NonNullable<typeof data.riasec>["scores"]]
          : k === "stability"
            ? (typeof data?.bigFive?.scores?.N === "number" ? 100 - data.bigFive.scores.N : undefined)
            : data?.bigFive?.scores?.[k as keyof NonNullable<typeof data.bigFive>["scores"]];
      out[k] = scoreToLevel(raw);
    }
    return out;
  }

  const mutation = useMutation({
    mutationFn: () => {
      const edits: SelfModelEdits = {};
      const rAuto = Object.values(riasec).every((v) => v === "auto");
      edits.riasec = rAuto ? "auto" : { levels: resolveLevels(riasec, "riasec") };
      const bAuto = Object.values(bigFive).every((v) => v === "auto");
      edits.big_five = bAuto ? "auto" : { levels: resolveLevels(bigFive, "big_five") };
      edits.narrative = narrative.trim() ? narrative.trim() : "auto";
      return updateSelfModel(edits);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["self-model", profile?.id] });
      onClose();
    },
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div
        className="max-h-[85vh] w-full max-w-md overflow-y-auto rounded-2xl bg-white p-5 shadow-xl dark:bg-slate-800"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-base font-bold text-slate-900 dark:text-slate-100">나의 성향 직접 정하기</h2>
        <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
          내가 정한 항목은 대화로 바뀌지 않아요. AI판단을 고르면 다시 대화로 파악해요.
        </p>

        <Section title="직업 흥미(RIASEC)" axes={RIASEC} state={riasec} setState={setRiasec} />
        <Section title="성격(Big Five)" axes={BIG_FIVE} state={bigFive} setState={setBigFive} />

        <div className="mt-4">
          <p className="mb-1 text-xs font-semibold text-slate-700 dark:text-slate-300">한 줄 자기소개</p>
          <textarea
            value={narrative}
            onChange={(e) => setNarrative(e.target.value)}
            rows={2}
            className="w-full rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
            placeholder={data?.narrativeSummary || "예: 문제를 깊이 파고드는 걸 좋아해요."}
          />
        </div>

        <div className="mt-5 flex justify-end gap-2">
          <button type="button" onClick={onClose} className="rounded-lg px-3 py-2 text-sm text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-700">취소</button>
          <button
            type="button"
            onClick={() => mutation.mutate()}
            disabled={mutation.isPending}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50"
          >
            {mutation.isPending ? "저장 중…" : "저장"}
          </button>
        </div>
      </div>
    </div>
  );
}

function Section({
  title, axes, state, setState,
}: {
  title: string;
  axes: readonly { key: string; label: string }[];
  state: Record<string, Seg>;
  setState: (s: Record<string, Seg>) => void;
}) {
  return (
    <div className="mt-4">
      <p className="mb-1.5 text-xs font-semibold text-slate-700 dark:text-slate-300">{title}</p>
      <div className="space-y-1.5">
        {axes.map((a) => (
          <div key={a.key} className="flex items-center gap-2">
            <span className="w-16 shrink-0 text-[11px] text-slate-600 dark:text-slate-300">{a.label}</span>
            <div className="flex flex-1 overflow-hidden rounded-lg border border-slate-200 dark:border-slate-700">
              {SEGS.map((seg) => (
                <button
                  key={seg.v}
                  type="button"
                  onClick={() => setState({ ...state, [a.key]: seg.v })}
                  className={
                    "flex-1 px-1 py-1 text-[11px] transition " +
                    (state[a.key] === seg.v
                      ? "bg-indigo-600 text-white"
                      : "bg-white text-slate-600 hover:bg-slate-50 dark:bg-slate-900 dark:text-slate-300")
                  }
                >
                  {seg.t}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
