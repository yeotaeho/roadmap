"use client";

// 펄스 섹터 상세 페이지 좌측 사이드바 — 분야별 트렌드 속도 카드 목록 네비게이션

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { SideNav } from "@/components/layout/SideNav";
import { usePulse } from "@/hooks/useDashboard";

export function PulseSectorSidebar() {
  const pathname = usePathname();
  const { data: sectors, isLoading, isError } = usePulse();
  // usePathname은 인코딩/정규화된 실경로 → 마지막 세그먼트만 비교해 slug 인코딩 차이에도 안정적으로 매칭.
  const activeSlug = pathname?.split("/").pop();

  return (
    <SideNav>
      <p className="px-2 pt-1 pb-2 text-[11px] font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">
        분야별 트렌드 속도
      </p>
      {isLoading && (
        <div className="flex flex-col gap-1 px-1" aria-hidden>
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-11 rounded-lg bg-slate-200/60 animate-pulse dark:bg-slate-800/60" />
          ))}
        </div>
      )}
      {isError && (
        <p className="px-2 py-1 text-xs text-slate-400">섹터 목록을 불러오지 못했습니다.</p>
      )}
      {(sectors ?? []).map((s) => {
        const href = `/dashboard/pulse/sectors/${s.sector_slug}`;
        const active = activeSlug === s.sector_slug;
        return (
          <Link
            key={s.sector_slug}
            href={href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "block rounded-lg border px-3 py-2 transition",
              active
                ? "border-indigo-200 bg-white shadow-sm dark:border-indigo-800 dark:bg-slate-800"
                : "border-transparent hover:bg-white/70 dark:hover:bg-slate-800/70"
            )}
          >
            <div className="flex items-center justify-between gap-2">
              <span
                className={cn(
                  "truncate text-sm font-medium",
                  active
                    ? "text-indigo-700 dark:text-indigo-300"
                    : "text-slate-600 dark:text-slate-300"
                )}
              >
                {s.sector_name}
              </span>
              <span className="shrink-0 text-sm font-bold text-slate-900 dark:text-slate-100">
                {s.score}
              </span>
            </div>
            {s.momentum_pct != null && (
              <span
                className={cn(
                  "mt-0.5 block text-xs font-semibold",
                  s.momentum_pct < 0 ? "text-rose-600" : "text-emerald-600"
                )}
              >
                {s.momentum_pct > 0 ? "+" : ""}
                {s.momentum_pct}%
              </span>
            )}
          </Link>
        );
      })}
    </SideNav>
  );
}
