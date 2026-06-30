// 성향·선호 선택 입력 섹션 — 자기완결형

"use client";

import { useEffect, useState } from "react";

import ChipSelect from "./ChipSelect";
import {
  COMPANY_SIZE_OPTIONS,
  WORK_STYLE_OPTIONS,
  WORK_TYPE_OPTIONS,
  WORK_VALUE_OPTIONS,
} from "@/data/personalizationOptions";
import { usePreferences, useUpsertPreferences } from "@/hooks/usePreferences";

export default function PreferencesSection({ className = "" }: { className?: string }) {
  const { data } = usePreferences();
  const upsert = useUpsertPreferences();
  const [workStyle, setWorkStyle] = useState<string>("");
  const [companySizePref, setCompanySizePref] = useState<string>("");
  const [workTypePref, setWorkTypePref] = useState<string>("");
  const [workValues, setWorkValues] = useState<string[]>([]);
  const [saved, setSaved] = useState(false);
  const [saveFailed, setSaveFailed] = useState(false);

  useEffect(() => {
    if (!data) return;
    setWorkStyle(data.workStyle ?? "");
    setCompanySizePref(data.companySizePref ?? "");
    setWorkTypePref(data.workTypePref ?? "");
    setWorkValues(data.workValues ?? []);
  }, [data]);

  const save = async () => {
    try {
      await upsert.mutateAsync({
        workStyle: workStyle || null,
        companySizePref: companySizePref || null,
        workTypePref: workTypePref || null,
        workValues,
      });
      setSaveFailed(false);
      setSaved(true);
      setTimeout(() => setSaved(false), 1500);
    } catch {
      setSaveFailed(true);
      setTimeout(() => setSaveFailed(false), 3000);
    }
  };

  return (
    <section className={`rounded-lg border border-gray-200 p-4 ${className}`}>
      <h3 className="text-sm font-semibold text-gray-900 mb-1">성향·선호 · 선택 입력</h3>
      <p className="text-xs text-gray-500 mb-3">채울수록 추천이 정확해져요.</p>
      <div className="space-y-3">
        <div>
          <label className="block text-xs text-gray-600 mb-1">일하는 스타일</label>
          <ChipSelect
            options={WORK_STYLE_OPTIONS}
            value={workStyle}
            onChange={(v) => setWorkStyle(v as string)}
          />
        </div>
        <div>
          <label className="block text-xs text-gray-600 mb-1">선호 기업 규모</label>
          <ChipSelect
            options={COMPANY_SIZE_OPTIONS}
            value={companySizePref}
            onChange={(v) => setCompanySizePref(v as string)}
          />
        </div>
        <div>
          <label className="block text-xs text-gray-600 mb-1">근무 형태</label>
          <ChipSelect
            options={WORK_TYPE_OPTIONS}
            value={workTypePref}
            onChange={(v) => setWorkTypePref(v as string)}
          />
        </div>
        <div>
          <label className="block text-xs text-gray-600 mb-1">직업 가치관 (복수 선택)</label>
          <ChipSelect
            options={WORK_VALUE_OPTIONS}
            value={workValues}
            multi
            onChange={(v) => setWorkValues(v as string[])}
          />
        </div>
        <button
          type="button"
          onClick={save}
          disabled={upsert.isPending}
          className="px-4 py-2 bg-red-600 text-white rounded-md text-sm hover:bg-red-700 disabled:opacity-50"
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
