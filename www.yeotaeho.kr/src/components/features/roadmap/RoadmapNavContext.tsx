"use client";

// 로드맵 사이드바(셸)와 RoadmapView가 공유하는 서브탭 상태 Context.

import React, { createContext, useContext, useMemo, useState } from "react";

export type RoadmapSubTab = "journey" | "archive";

interface RoadmapNavValue {
  subTab: RoadmapSubTab;
  setSubTab: (t: RoadmapSubTab) => void;
}

const RoadmapNavContext = createContext<RoadmapNavValue | null>(null);

export function RoadmapNavProvider({ children }: { children: React.ReactNode }) {
  const [subTab, setSubTab] = useState<RoadmapSubTab>("journey");
  const value = useMemo(() => ({ subTab, setSubTab }), [subTab]);
  return <RoadmapNavContext.Provider value={value}>{children}</RoadmapNavContext.Provider>;
}

export function useRoadmapNav(): RoadmapNavValue {
  const ctx = useContext(RoadmapNavContext);
  if (!ctx) {
    throw new Error("useRoadmapNav must be used within a RoadmapNavProvider");
  }
  return ctx;
}
