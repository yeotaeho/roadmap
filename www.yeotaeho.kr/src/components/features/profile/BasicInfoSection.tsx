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
  "w-full px-3 py-2 border border-border rounded-md bg-card text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500";

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
  const [yearError, setYearError] = useState(false);

  const currentYear = new Date().getFullYear();

  useEffect(() => {
    if (!data) return;
    setBirthYear(data.birthYear ? String(data.birthYear) : "");
    setGender(data.gender ?? "");
    setRegion(data.region ?? "");
    setCurrentStatus(data.currentStatus ?? "");
    setEducationLevel(data.educationLevel ?? "");
  }, [data]);

  const save = async () => {
    // 출생연도 검증 — 4자리 연도만(생년월일 8자리 등 잘못된 입력 차단).
    const trimmed = birthYear.trim();
    let yearValue: number | null = null;
    if (trimmed !== "") {
      const n = Number(trimmed);
      if (!Number.isInteger(n) || n < 1900 || n > currentYear) {
        setYearError(true);
        setTimeout(() => setYearError(false), 3000);
        return;
      }
      yearValue = n;
    }
    try {
      await upsert.mutateAsync({
        birthYear: yearValue,
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
    <section className={`rounded-lg border border-border bg-card p-4 ${className}`}>
      <h3 className="text-sm font-semibold text-foreground mb-1">기본정보 · 선택 입력</h3>
      <p className="text-xs text-muted-foreground mb-3">채울수록 추천이 정확해져요.</p>
      <div className="space-y-3">
        <div>
          <label className="block text-xs text-muted-foreground mb-1">출생연도</label>
          <input
            type="number"
            value={birthYear}
            min={1900}
            max={currentYear}
            onChange={(e) => setBirthYear(e.target.value)}
            placeholder="예) 1999"
            className={inputCls}
          />
          {yearError && (
            <p className="text-red-600 text-xs mt-1">
              출생연도를 4자리로 입력해 주세요 (예: 1999).
            </p>
          )}
        </div>
        <div>
          <label className="block text-xs text-muted-foreground mb-1">성별</label>
          <ChipSelect
            options={GENDER_OPTIONS}
            value={gender}
            onChange={(v) => setGender(v as string)}
          />
        </div>
        <div>
          <label className="block text-xs text-muted-foreground mb-1">현재 상태</label>
          <ChipSelect
            options={CURRENT_STATUS_OPTIONS}
            value={currentStatus}
            onChange={(v) => setCurrentStatus(v as string)}
          />
        </div>
        <div>
          <label className="block text-xs text-muted-foreground mb-1">최종 학력</label>
          <ChipSelect
            options={EDUCATION_OPTIONS}
            value={educationLevel}
            onChange={(v) => setEducationLevel(v as string)}
          />
        </div>
        <div>
          <label className="block text-xs text-muted-foreground mb-1">거주 지역</label>
          <input
            value={region}
            maxLength={50}
            onChange={(e) => setRegion(e.target.value)}
            placeholder="예) 서울"
            className={inputCls}
          />
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
