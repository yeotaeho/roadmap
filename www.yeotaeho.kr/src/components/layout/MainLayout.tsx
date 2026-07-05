"use client";

import React, { useEffect, useState } from "react";
import { getCurrentUser } from "@/lib/api/user";
import { getUserName } from "@/utils/tokenStorage";
import { useAuth } from "@/hooks/useStore";
import { useStore } from "@/store";
import { usePathname } from "next/navigation";
import { Header } from "./Header";
import { MainTabBar } from "./MainTabBar";
import { Footer } from "./Footer";
import { DashboardNavProvider } from "@/components/features/dashboard/DashboardNavContext";
import { DashboardSidebar } from "@/components/features/dashboard/DashboardSidebar";
import { RoadmapNavProvider } from "@/components/features/roadmap/RoadmapNavContext";
import { RoadmapSidebar } from "@/components/features/roadmap/RoadmapSidebar";
import { ConsultSidebar } from "@/components/features/consult/ConsultSidebar";
import { CoachSidebar } from "@/components/features/coach/CoachSidebar";

export function MainLayout({ children }: { children: React.ReactNode }) {
  const [userName, setUserName] = useState<string | null>(null);
  const { token, isAuthenticated } = useAuth();
  const pathname = usePathname();
  // 개별 액션 셀렉트 — zustand 액션은 고정 참조. 객체 셀렉터(useUserActions)는 매 렌더 새 객체라 무한 루프.
  const setProfile = useStore((s) => s.setProfile);
  const clearProfile = useStore((s) => s.clearProfile);

  useEffect(() => {
    const fetchUserInfo = async () => {
      if (token && isAuthenticated) {
        try {
          const userInfo = await getCurrentUser();
          if (userInfo) {
            setUserName(userInfo.nickname || userInfo.name);
            // store profile 하이드레이션 — Sync·Chance 등 profile?.id 게이트 활성화(로그인 후에만 설정되던 미싱 링크).
            setProfile({
              id: userInfo.id,
              name: userInfo.nickname || userInfo.name || userInfo.email || "",
              email: userInfo.email || "",
              avatar: userInfo.profileImage || undefined,
            });
          } else {
            setUserName(getUserName(token));
          }
        } catch {
          setUserName(getUserName(token));
        }
      } else {
        setUserName(null);
        clearProfile();
      }
    };
    fetchUserInfo();
  }, [token, isAuthenticated, setProfile, clearProfile]);

  const shell = (sidebar: React.ReactNode) => (
    <div className="flex flex-1 min-h-0 flex-col lg:flex-row">
      {sidebar}
      <div className="flex flex-1 min-w-0 flex-col">
        <MainTabBar />
        <main className="flex-1 w-full max-w-[1480px] mx-auto px-4 sm:px-6 lg:px-8 py-6">
          {children}
        </main>
        <Footer />
      </div>
    </div>
  );

  // 라우트별 좌측 사이드바 — 상태를 쓰는 페이지는 해당 Provider로 감싸 공유.
  // 계약: 컨텍스트 소비 뷰(DashboardView·RoadmapView)는 각 단일 라우트에서만 마운트된다.
  // 하위 라우트를 추가하면(예: /roadmap/[id]) 해당 브랜치를 startsWith로 넓혀 Provider 밖 렌더(throw)를 막을 것.
  let body: React.ReactNode;
  if (pathname === "/") {
    body = <DashboardNavProvider>{shell(<DashboardSidebar />)}</DashboardNavProvider>;
  } else if (pathname === "/roadmap") {
    body = <RoadmapNavProvider>{shell(<RoadmapSidebar />)}</RoadmapNavProvider>;
  } else if (pathname === "/consult") {
    body = shell(<ConsultSidebar />);
  } else if (pathname?.startsWith("/coach")) {
    body = shell(<CoachSidebar />);
  } else {
    body = shell(null);
  }

  return (
    <div className="min-h-screen flex flex-col bg-gray-50 font-sans dark:bg-slate-950">
      <Header
        userName={userName}
        onLogout={() => setUserName(null)}
      />
      {body}
    </div>
  );
}
