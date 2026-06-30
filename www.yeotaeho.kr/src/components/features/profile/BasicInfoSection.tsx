// 기본정보(데모그래픽) 선택 입력 섹션 — 자기완결형

"use client";

import { useEffect, useState } from "react";

import ChipSelect from "./ChipSelect";
import {
  CURRENT_STATUS_OPTIONS,
  EDUCATION_OPTIONS,
  GENDER_OPTIONS,
} from "@/data/personalizationOptions";
import { useProfile, useUpsertProfile } from "@/hooks/useProfile";

const inputCls =
  "w-full px-3 py-2 border border-gray-300 rounded-md bg-white text-sm focus:outline-none focus:ring-2 focus:ring-red-500";

export default function BasicInfoSection({ className = "" }: { className?: string }) {
  const { data } = useProfile();
  const upsert = useUpsertProfile();
  const [birthYear, setBirthYear] = useState<string>("");
  const [gender, setGender] = useState<string>("");
  const [region, setRegion] = useState<string>("");
  const [currentStatus, setCurrentStatus] = useState<string>("");
  const [educationLevel, setEducationLevel] = useState<string>("");
  const [saved, setSaved] = useState(false);
  const [saveFailed, setSaveFailed] = useState(false);

  useEffect(() => {
    if (!data) return;
    setBirthYear(data.birthYear ? String(data.birthYear) : "");
    setGender(data.gender ?? "");
    setRegion(data.region ?? "");
    setCurrentStatus(data.currentStatus ?? "");
    setEducationLevel(data.educationLevel ?? "");
  }, [data]);

  const save = async () => {
    try {
      await upsert.mutateAsync({
        birthYear: birthYear === "" ? null : Number(birthYear),
        gender: gender || null,
        region: region || null,
        currentStatus: currentStatus || null,
        educationLevel: educationLevel || null,
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
      <h3 className="text-sm font-semibold text-gray-900 mb-1">기본정보 · 선택 입력</h3>
      <p className="text-xs text-gray-500 mb-3">채울수록 추천이 정확해져요.</p>
      <div className="space-y-3">
        <div>
          <label className="block text-xs text-gray-600 mb-1">출생연도</label>
          <input
            type="number"
            value={birthYear}
            onChange={(e) => setBirthYear(e.target.value)}
            placeholder="예) 1999"
            className={inputCls}
          />
        </div>
        <div>
          <label className="block text-xs text-gray-600 mb-1">성별</label>
          <ChipSelect
            options={GENDER_OPTIONS}
            value={gender}
            onChange={(v) => setGender(v as string)}
          />
        </div>
        <div>
          <label className="block text-xs text-gray-600 mb-1">현재 상태</label>
          <ChipSelect
            options={CURRENT_STATUS_OPTIONS}
            value={currentStatus}
            onChange={(v) => setCurrentStatus(v as string)}
          />
        </div>
        <div>
          <label className="block text-xs text-gray-600 mb-1">최종 학력</label>
          <ChipSelect
            options={EDUCATION_OPTIONS}
            value={educationLevel}
            onChange={(v) => setEducationLevel(v as string)}
          />
        </div>
        <div>
          <label className="block text-xs text-gray-600 mb-1">거주 지역</label>
          <input
            value={region}
            onChange={(e) => setRegion(e.target.value)}
            placeholder="예) 서울"
            className={inputCls}
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
