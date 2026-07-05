"use client";

// 앱-셸 좌측 사이드바 공통 셸 — 대시보드/로드맵/상담/코치가 동일 스타일을 공유.

import React from "react";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

export function SideNav({ children }: { children: React.ReactNode }) {
  return (
    <aside className="shrink-0 border-b border-indigo-100 bg-indigo-50/70 dark:border-slate-700 dark:bg-slate-900 lg:w-56 lg:border-b-0 lg:border-r">
      <nav className="flex h-full flex-col gap-0.5 p-2.5">{children}</nav>
    </aside>
  );
}

export function SideNavButton({
  icon: Icon,
  label,
  active = false,
  onClick,
}: {
  icon?: LucideIcon;
  label: string;
  active?: boolean;
  onClick?: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-current={active ? "page" : undefined}
      className={cn(
        "flex items-center gap-2.5 rounded-lg px-3 py-2.5 text-sm transition text-left",
        active
          ? "bg-white font-semibold text-indigo-700 shadow-sm ring-1 ring-indigo-100 dark:bg-slate-800 dark:text-indigo-300 dark:ring-slate-700"
          : "font-medium text-slate-600 hover:bg-white/70 hover:text-indigo-700 dark:text-slate-300 dark:hover:bg-slate-800/80 dark:hover:text-indigo-300"
      )}
    >
      {Icon && <Icon className="w-4 h-4 shrink-0" aria-hidden />}
      <span className="flex-1">{label}</span>
    </button>
  );
}
