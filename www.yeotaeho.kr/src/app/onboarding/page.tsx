// 로그인 후 선택 온보딩 — 프로필 섹션 재사용, 건너뛰기 가능

"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import BasicInfoSection from "@/components/features/profile/BasicInfoSection";
import PreferencesSection from "@/components/features/profile/PreferencesSection";
import { PersonaForm } from "@/components/features/profile/PersonaForm";
import InterestSection from "@/components/features/profile/InterestSection";
import { markOnboardingDone } from "@/lib/onboarding";
import { useAuth } from "@/hooks/useStore";

export default function OnboardingPage() {
  const router = useRouter();
  const { isAuthenticated } = useAuth();

  useEffect(() => {
    if (!isAuthenticated) router.replace("/login");
  }, [isAuthenticated, router]);

  const finish = () => {
    markOnboardingDone();
    router.push("/");
  };

  return (
    <div className="min-h-screen bg-white px-4 py-10">
      <div className="max-w-2xl mx-auto">
        <h1 className="text-2xl font-bold text-gray-900 mb-1">프로필을 채워볼까요?</h1>
        <p className="text-sm text-gray-500 mb-6">선택 입력이에요. 채울수록 추천이 정확해지고, 언제든 건너뛸 수 있어요.</p>
        <div className="space-y-4">
          <BasicInfoSection />
          <PreferencesSection />
          <PersonaForm />
          <InterestSection />
        </div>
        <div className="flex gap-3 mt-8">
          <button onClick={finish} className="px-5 py-2 bg-red-600 text-white rounded-md hover:bg-red-700">완료</button>
          <button onClick={finish} className="px-5 py-2 border border-gray-300 text-gray-700 rounded-md hover:bg-gray-50">나중에 입력</button>
        </div>
      </div>
    </div>
  );
}
