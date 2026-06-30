// 프로필 완성도 미터 — 선택 데이터 채움 비율을 추천 정확도 넛지로 표시

"use client";

import { useQuery } from "@tanstack/react-query";

import { Progress } from "@/components/ui/progress";
import { usePersona } from "@/hooks/usePersona";
import { usePreferences } from "@/hooks/usePreferences";
import { useProfile } from "@/hooks/useProfile";
import { getSyncProfile } from "@/lib/api/user";

function useSyncProfileQuery() {
  return useQuery({
    queryKey: ["syncProfile"],
    queryFn: getSyncProfile,
    staleTime: 5 * 60 * 1000,
    retry: 1,
  });
}

export default function CompletionMeter() {
  const { data: profile } = useProfile();
  const { data: prefs } = usePreferences();
  const { data: persona } = usePersona();
  const { data: sync } = useSyncProfileQuery();

  const filled = [
    // 기본정보 5
    !!profile?.birthYear,
    !!profile?.gender,
    !!profile?.region,
    !!profile?.currentStatus,
    !!profile?.educationLevel,
    // 성향 4
    !!prefs?.workStyle,
    !!prefs?.companySizePref,
    !!prefs?.workTypePref,
    (prefs?.workValues?.length ?? 0) > 0,
    // 스펙 4
    (persona?.skills?.length ?? 0) > 0,
    (persona?.certifications?.length ?? 0) > 0,
    (persona?.languages?.length ?? 0) > 0,
    (persona?.projects?.length ?? 0) > 0,
    // 관심 2
    !!sync?.targetJob,
    (sync?.interestKeywords?.length ?? 0) > 0,
  ];

  const total = filled.length; // 15
  const done = filled.filter(Boolean).length;
  const pct = Math.round((done / total) * 100);

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 mb-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-semibold text-gray-900">프로필 완성도</span>
        <span className="text-sm font-semibold text-red-600">{pct}%</span>
      </div>
      <Progress value={pct} />
      <p className="text-xs text-gray-500 mt-2">채울수록 Sync·Chance 추천이 정확해져요.</p>
    </div>
  );
}
