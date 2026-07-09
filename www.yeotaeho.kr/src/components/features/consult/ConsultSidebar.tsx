"use client";

// 상담 좌측 사이드바 — 새 채팅 + 세션 목록(전환).

import { MessageSquarePlus, MessageCircle } from "lucide-react";
import { SideNav, SideNavButton } from "@/components/layout/SideNav";
import { useConsultNav } from "./ConsultNavContext";

export function ConsultSidebar() {
  const { sessionId, sessions, selectSession, startNewChat } = useConsultNav();
  return (
    <SideNav>
      <SideNavButton icon={MessageSquarePlus} label="새 채팅" onClick={startNewChat} active={sessionId === null} />
      {sessions.map((s) => (
        <SideNavButton
          key={s.id}
          icon={MessageCircle}
          label={s.title ?? "대화"}
          active={sessionId === s.id}
          onClick={() => selectSession(s.id)}
        />
      ))}
    </SideNav>
  );
}
