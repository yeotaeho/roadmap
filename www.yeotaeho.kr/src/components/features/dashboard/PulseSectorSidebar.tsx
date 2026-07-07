"use client";

// 펄스 섹터 상세 페이지 좌측 사이드바 — 분야별 트렌드 속도 카드 목록 네비게이션

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { SideNav } from "@/components/layout/SideNav";
import { usePulse } from "@/hooks/useDashboard";

export function PulseSectorSidebar() {
  const pathname = usePathname();
  const { data: sectors } = usePulse();

  return (
    <SideNav>
      <p className="px-2 pt-1 pb-2 text-[11px] font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">
        분야별 트렌드 속도
      </p>
      {(sectors ?? []).map((s) => {
        const href = `/dashboard/pulse/sectors/${s.sector_slug}`;
        const active = pathname === href;
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
