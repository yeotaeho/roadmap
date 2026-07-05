"use client";

// 대시보드 사이드바(셸)와 콘텐츠(DashboardView)가 공유하는 네비게이션 상태 Context.

import React, { createContext, useContext, useMemo, useState } from "react";
import { Activity, Compass, Link2, Rocket, type LucideIcon } from "lucide-react";
import type { PulseSectionId } from "./PulseTab";

export const SUB_TABS = [
  { id: "pulse", label: "펄스", fullLabel: "실시간 펄스", icon: Activity },
  { id: "gap", label: "블루오션", fullLabel: "블루오션", icon: Compass },
  { id: "sync", label: "싱크", fullLabel: "싱크로율", icon: Link2 },
  { id: "chance", label: "찬스", fullLabel: "다이렉트 찬스", icon: Rocket },
] as const satisfies ReadonlyArray<{
  id: string;
  label: string;
  fullLabel: string;
  icon: LucideIcon;
}>;

export type TabId = (typeof SUB_TABS)[number]["id"];

// 펄스 탭에서 드롭다운으로 선택하는 세부 섹션 목록.
export const PULSE_SECTIONS: { id: PulseSectionId; label: string }[] = [
  { id: "overview", label: "개요" },
  { id: "forecast", label: "14일 전망" },
  { id: "causal", label: "인과관계 체인" },
  { id: "momentum", label: "연간 모멘텀 트렌드" },
  { id: "share", label: "관심 점유율" },
  { id: "heatmap", label: "Top 섹터 히트맵" },
  { id: "crossover", label: "세대교체 크로스오버" },
  { id: "keywords", label: "트렌딩 키워드" },
];

interface DashboardNavValue {
  activeTab: TabId;
  setActiveTab: (tab: TabId) => void;
  pulseSection: PulseSectionId;
  setPulseSection: (section: PulseSectionId) => void;
  pulseOpen: boolean;
  setPulseOpen: React.Dispatch<React.SetStateAction<boolean>>;
}

const DashboardNavContext = createContext<DashboardNavValue | null>(null);

export function DashboardNavProvider({ children }: { children: React.ReactNode }) {
  const [activeTab, setActiveTab] = useState<TabId>("pulse");
  const [pulseSection, setPulseSection] = useState<PulseSectionId>("overview");
  const [pulseOpen, setPulseOpen] = useState(true);

  const value = useMemo(
    () => ({ activeTab, setActiveTab, pulseSection, setPulseSection, pulseOpen, setPulseOpen }),
    [activeTab, pulseSection, pulseOpen],
  );

  return <DashboardNavContext.Provider value={value}>{children}</DashboardNavContext.Provider>;
}

export function useDashboardNav(): DashboardNavValue {
  const ctx = useContext(DashboardNavContext);
  if (!ctx) {
    throw new Error("useDashboardNav must be used within a DashboardNavProvider");
  }
  return ctx;
}
