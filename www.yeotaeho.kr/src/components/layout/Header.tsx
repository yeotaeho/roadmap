"use client";

import React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useStore";

interface HeaderProps {
  userName?: string | null;
  onLogout?: () => void;
}

export const Header: React.FC<HeaderProps> = ({ userName, onLogout }) => {
  const router = useRouter();
  const { isAuthenticated, logoutAsync } = useAuth();

  const handleLogout = async () => {
    try {
      await logoutAsync();
      onLogout?.();
      router.push("/");
      router.refresh();
    } catch (error) {
      console.error("로그아웃 처리 중 오류:", error);
    }
  };

  return (
    <header className="sticky top-0 z-50 bg-white shadow-md border-b border-gray-100 dark:bg-slate-950 dark:border-slate-800">
      <div className="max-w-[1480px] mx-auto px-4 sm:px-6 lg:px-8 py-3 flex justify-between items-center">
        <Link href="/" className="text-lg sm:text-xl font-extrabold text-gray-900 tracking-tight dark:text-slate-100">
          청년 인사이트
          <span className="font-normal text-xs sm:text-sm block -mt-0.5 text-gray-500 dark:text-slate-400">
            Global Pulse
          </span>
        </Link>

        <div className="flex items-center gap-2 sm:gap-3">
          {isAuthenticated ? (
            <>
              <Link
                href="/profile"
                className="px-2 sm:px-3 py-2 text-sm text-gray-700 font-medium hover:text-indigo-600 transition truncate max-w-[120px] sm:max-w-none dark:text-slate-300 dark:hover:text-indigo-400"
              >
                {userName || "사용자"}님
              </Link>
              <button
                type="button"
                onClick={handleLogout}
                className="px-3 sm:px-4 py-2 text-sm text-white bg-indigo-600 hover:bg-indigo-700 transition font-medium rounded-full"
              >
                로그아웃
              </button>
            </>
          ) : (
            <>
              <Link
                href="/login"
                className="px-2 sm:px-3 py-2 text-sm text-gray-700 hover:text-indigo-600 transition font-medium dark:text-slate-300 dark:hover:text-indigo-400"
              >
                로그인
              </Link>
              <Link
                href="/signup"
                className="px-3 sm:px-4 py-2 text-sm text-white bg-indigo-600 hover:bg-indigo-700 transition font-medium rounded-full"
              >
                회원가입
              </Link>
            </>
          )}
        </div>
      </div>
    </header>
  );
};
