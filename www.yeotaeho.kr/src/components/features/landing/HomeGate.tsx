// 루트 "/" 분기 게이트 — 비로그인은 랜딩, 로그인은 기존 대시보드 셸 (깜빡임 방지 3-상태)
"use client";

import { useEffect, useState } from "react";
import { useStore } from "@/store";
import { MainLayout } from "@/components/layout/MainLayout";
import { DashboardView } from "@/components/features/dashboard/DashboardView";
import { LandingView } from "./LandingView";
import { LANDING_COPY } from "./landing.copy";

/** 로그인 이력 힌트 — authSlice가 login/setToken 시 기록 (첫 페인트 분기용) */
function readAuthHint(): boolean {
  try {
    return localStorage.getItem("yi-auth-hint") === "1";
  } catch {
    return false;
  }
}

/** 인증 복원 대기 중 브랜드 스플래시 — 로그인 유저에게 랜딩이 번쩍이는 것을 방지 */
function BrandSplash() {
  return (
    <div
      role="status"
      aria-live="polite"
      className="flex min-h-screen flex-col items-center justify-center gap-2 bg-gray-50 dark:bg-slate-950"
    >
      <span className="sr-only">로그인 상태를 확인하는 중</span>
      <span className="text-2xl font-extrabold tracking-tight text-slate-900 dark:text-white">
        {LANDING_COPY.brand.name}
      </span>
      <span className="text-sm font-medium text-slate-400 dark:text-slate-500">
        {LANDING_COPY.brand.sub}
      </span>
    </div>
  );
}

export function HomeGate() {
  const isAuthenticated = useStore((s) => s.isAuthenticated);
  const isAuthResolved = useStore((s) => s.isAuthResolved);
  const [mounted, setMounted] = useState(false);
  // 마운트 시 1회만 읽음 — 이후 변화는 store 상태(isAuthResolved)가 담당
  const [hasAuthHint] = useState(readAuthHint);

  useEffect(() => {
    setMounted(true);
  }, []);

  // 분기 확정(인증됨 또는 복원 완료) 시 인라인 스크립트가 걸어둔 랜딩 숨김 해제
  // (page.tsx의 yi-auth-pending — 로그아웃 후 게스트 랜딩이 hidden으로 남지 않도록 필수)
  useEffect(() => {
    if (isAuthenticated || isAuthResolved) {
      document.documentElement.classList.remove("yi-auth-pending");
    }
  }, [isAuthenticated, isAuthResolved]);

  // 서버 렌더·첫 클라이언트 렌더는 항상 랜딩 — 게스트 SEO/LCP 확보 (hydration mismatch 방지)
  // 로그인 이력자는 yi-auth-pending CSS가 첫 페인트 전에 랜딩을 가린다.
  if (!mounted) return <LandingView />;

  if (isAuthenticated) {
    return (
      <MainLayout>
        <DashboardView />
      </MainLayout>
    );
  }

  // 로그인 이력이 있으면 복원 완료까지 잠시 스플래시 (보통 수백 ms)
  if (!isAuthResolved && hasAuthHint) return <BrandSplash />;

  return <LandingView />;
}
