"use client";

import React, { useEffect, useState } from "react";
import { getCurrentUser } from "@/lib/api/user";
import { getUserName } from "@/utils/tokenStorage";
import { useAuth, useUserActions } from "@/hooks/useStore";
import { Header } from "./Header";
import { MainTabBar } from "./MainTabBar";
import { Footer } from "./Footer";

export function MainLayout({ children }: { children: React.ReactNode }) {
  const [userName, setUserName] = useState<string | null>(null);
  const { token, isAuthenticated } = useAuth();
  const { setProfile, clearProfile } = useUserActions();

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

  return (
    <div className="min-h-screen flex flex-col bg-gray-50 font-sans dark:bg-slate-950">
      <Header
        userName={userName}
        onLogout={() => setUserName(null)}
      />
      <MainTabBar />
      <main className="flex-1 w-full max-w-[1480px] mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {children}
      </main>
      <Footer />
    </div>
  );
}
