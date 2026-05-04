"use client";

import React, { useEffect, useState } from "react";
import { getCurrentUser } from "@/lib/api/user";
import { getUserName } from "@/utils/tokenStorage";
import { useAuth } from "@/hooks/useStore";
import { Header } from "./Header";
import { MainTabBar } from "./MainTabBar";
import { Footer } from "./Footer";

export function MainLayout({ children }: { children: React.ReactNode }) {
  const [userName, setUserName] = useState<string | null>(null);
  const { token, isAuthenticated } = useAuth();

  useEffect(() => {
    const fetchUserInfo = async () => {
      if (token && isAuthenticated) {
        try {
          const userInfo = await getCurrentUser();
          if (userInfo) {
            setUserName(userInfo.nickname || userInfo.name);
          } else {
            setUserName(getUserName(token));
          }
        } catch {
          setUserName(getUserName(token));
        }
      } else {
        setUserName(null);
      }
    };
    fetchUserInfo();
  }, [token, isAuthenticated]);

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
