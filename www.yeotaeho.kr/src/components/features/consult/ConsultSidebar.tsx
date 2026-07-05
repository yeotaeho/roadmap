"use client";

// AI 상담실 좌측 사이드바 — 현재는 단일 상담 대화 뷰(레이아웃 일관성용 틀).

import { MessageCircle } from "lucide-react";
import { SideNav, SideNavButton } from "@/components/layout/SideNav";

export function ConsultSidebar() {
  return (
    <SideNav>
      <SideNavButton icon={MessageCircle} label="상담 대화" active />
    </SideNav>
  );
}
