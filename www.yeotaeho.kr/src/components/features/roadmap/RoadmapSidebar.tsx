"use client";

// 전략 로드맵 좌측 사이드바 — 여정 개요 / 플래너 / 노트 서브탭 네비게이션. (성장 아카이브는 플래너 토글로 통합)

import { KanbanSquare, Map, NotebookPen, type LucideIcon } from "lucide-react";
import { SideNav, SideNavButton } from "@/components/layout/SideNav";
import { useRoadmapNav, type RoadmapSubTab } from "./RoadmapNavContext";

const ROADMAP_TABS: { id: RoadmapSubTab; label: string; icon: LucideIcon }[] = [
  { id: "journey", label: "여정 개요", icon: Map },
  { id: "planner", label: "플래너", icon: KanbanSquare },
  { id: "notes", label: "노트", icon: NotebookPen },
];

export function RoadmapSidebar() {
  const { subTab, setSubTab } = useRoadmapNav();
  return (
    <SideNav>
      {ROADMAP_TABS.map((t) => (
        <SideNavButton
          key={t.id}
          icon={t.icon}
          label={t.label}
          active={subTab === t.id}
          onClick={() => setSubTab(t.id)}
        />
      ))}
    </SideNav>
  );
}
