"use client";

// 전략 로드맵 좌측 사이드바 — 여정 개요 / 성장 아카이브 서브탭 네비게이션.

import { CalendarDays, KanbanSquare, Map, NotebookPen, type LucideIcon } from "lucide-react";
import { SideNav, SideNavButton } from "@/components/layout/SideNav";
import { useRoadmapNav, type RoadmapSubTab } from "./RoadmapNavContext";

const ROADMAP_TABS: { id: RoadmapSubTab; label: string; icon: LucideIcon }[] = [
  { id: "journey", label: "여정 개요", icon: Map },
  { id: "planner", label: "플래너", icon: KanbanSquare },
  { id: "notes", label: "노트", icon: NotebookPen },
  { id: "archive", label: "성장 아카이브", icon: CalendarDays },
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
