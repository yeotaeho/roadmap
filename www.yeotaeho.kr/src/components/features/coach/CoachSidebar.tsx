"use client";

// AI 코치 좌측 사이드바 — 준비 중 플레이스홀더(레이아웃 일관성용 틀).

import { Sparkles } from "lucide-react";
import { SideNav, SideNavButton } from "@/components/layout/SideNav";

export function CoachSidebar() {
  return (
    <SideNav>
      <SideNavButton icon={Sparkles} label="AI 코치" active />
    </SideNav>
  );
}
