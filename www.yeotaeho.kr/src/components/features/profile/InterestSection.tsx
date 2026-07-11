// 관심 분야·직무 선택 입력 섹션 — 자기완결형

"use client";

import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import ChipSelect from "./ChipSelect";
import { INTEREST_SECTORS, JOB_FAMILIES } from "@/data/personalizationOptions";
import { getSyncProfile, upsertSyncProfile } from "@/lib/api/user";

function useSyncProfile() {
  return useQuery({
    queryKey: ["syncProfile"],
    queryFn: getSyncProfile,
    staleTime: 5 * 60 * 1000,
    retry: 1,
  });
}

function useUpsertSyncProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: upsertSyncProfile,
    onSuccess: (saved) => {
      if (saved) qc.setQueryData(["syncProfile"], saved);
    },
  });
}

const inputCls =
  "w-full px-3 py-2 border border-border rounded-md bg-card text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500";

const SECTOR_VALUES = new Set(INTEREST_SECTORS.map((o) => o.value));
const JOB_VALUES = new Set(JOB_FAMILIES.map((o) => o.value));

export default function InterestSection({ className = "" }: { className?: string }) {
  const { data } = useSyncProfile();
  const upsert = useUpsertSyncProfile();

  const [targetJob, setTargetJob] = useState<string>("");
  // interestKeywords: 섹터 + 직무 + 커스텀 키워드 통합 관리
  const [selectedSectors, setSelectedSectors] = useState<string[]>([]);
  const [selectedJobs, setSelectedJobs] = useState<string[]>([]);
  const [customKeywords, setCustomKeywords] = useState<string[]>([]);
  const [customInput, setCustomInput] = useState<string>("");
  const [saved, setSaved] = useState(false);
  const [saveFailed, setSaveFailed] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  // 서버 데이터 도착/갱신 시 입력값 동기화 — 렌더 중 이전 data 와 비교(효과 대체).
  const [prevData, setPrevData] = useState(data);
  if (data && data !== prevData) {
    setPrevData(data);
    setTargetJob(data.targetJob ?? "");
    const kws = data.interestKeywords ?? [];
    setSelectedSectors(kws.filter((k) => SECTOR_VALUES.has(k)));
    setSelectedJobs(kws.filter((k) => JOB_VALUES.has(k)));
    setCustomKeywords(kws.filter((k) => !SECTOR_VALUES.has(k) && !JOB_VALUES.has(k)));
  }

  const addCustom = () => {
    const v = customInput.trim();
    if (!v) return;
    if (!customKeywords.includes(v)) setCustomKeywords((prev) => [...prev, v]);
    setCustomInput("");
    inputRef.current?.focus();
  };

  const removeCustom = (kw: string) =>
    setCustomKeywords((prev) => prev.filter((k) => k !== kw));

  const handleCustomKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      addCustom();
    }
  };

  const save = async () => {
    const interestKeywords = [...selectedSectors, ...selectedJobs, ...customKeywords];
    const result = await upsert.mutateAsync({ targetJob: targetJob || null, interestKeywords });
    if (!result) {
      setSaveFailed(true);
      setTimeout(() => setSaveFailed(false), 3000);
      return;
    }
    setSaved(true);
    setTimeout(() => setSaved(false), 1500);
  };

  return (
    <section className={`rounded-lg border border-border bg-card p-4 ${className}`}>
      <h3 className="text-sm font-semibold text-foreground mb-1">관심 분야 · 직무</h3>
      <p className="text-xs text-muted-foreground mb-3">채울수록 추천이 정확해져요.</p>
      <div className="space-y-3">
        <div>
          <label className="block text-xs text-muted-foreground mb-1">목표 직무</label>
          <input
            value={targetJob}
            onChange={(e) => setTargetJob(e.target.value)}
            placeholder="예) AI 엔지니어"
            className={inputCls}
          />
        </div>
        <div>
          <label className="block text-xs text-muted-foreground mb-1">관심 산업 (복수 선택)</label>
          <ChipSelect
            options={INTEREST_SECTORS}
            value={selectedSectors}
            multi
            onChange={(v) => setSelectedSectors(v as string[])}
          />
        </div>
        <div>
          <label className="block text-xs text-muted-foreground mb-1">관심 직무군 (복수 선택)</label>
          <ChipSelect
            options={JOB_FAMILIES}
            value={selectedJobs}
            multi
            onChange={(v) => setSelectedJobs(v as string[])}
          />
        </div>
        <div>
          <label className="block text-xs text-muted-foreground mb-1">기타 키워드 (Enter로 추가)</label>
          <div className="flex gap-2">
            <input
              ref={inputRef}
              value={customInput}
              onChange={(e) => setCustomInput(e.target.value)}
              onKeyDown={handleCustomKeyDown}
              placeholder="예) 탄소중립"
              className={inputCls}
            />
            <button
              type="button"
              onClick={addCustom}
              className="px-3 py-2 bg-muted text-foreground rounded-md text-sm hover:bg-accent whitespace-nowrap"
            >
              추가
            </button>
          </div>
          {customKeywords.length > 0 && (
            <div className="flex flex-wrap gap-2 mt-2">
              {customKeywords.map((kw) => (
                <span
                  key={kw}
                  className="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-muted border border-border text-sm text-foreground"
                >
                  {kw}
                  <button
                    type="button"
                    onClick={() => removeCustom(kw)}
                    className="text-muted-foreground hover:text-red-600 leading-none"
                  >
                    ×
                  </button>
                </span>
              ))}
            </div>
          )}
        </div>
        <button
          type="button"
          onClick={save}
          disabled={upsert.isPending}
          className="px-4 py-2 bg-indigo-600 text-white rounded-md text-sm hover:bg-indigo-700 disabled:opacity-50"
        >
          {upsert.isPending ? "저장 중…" : saved ? "저장됨" : "저장"}
        </button>
        {saveFailed && (
          <p className="text-red-600 text-xs mt-1">저장에 실패했어요. 다시 시도해 주세요.</p>
        )}
      </div>
    </section>
  );
}
