"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  MessageCircle,
  Map,
  Sparkles,
} from "lucide-react";
import { ThemeToggle } from "./ThemeToggle";

const TABS = [
  { href: "/", label: "인사이트", shortLabel: "인사이트", icon: LayoutDashboard },
  { href: "/consult", label: "AI 상담실", shortLabel: "상담", icon: MessageCircle },
  { href: "/roadmap", label: "전략 로드맵", shortLabel: "로드맵", icon: Map },
  { href: "/coach", label: "AI 코치", shortLabel: "코치", icon: Sparkles },
] as const;

export function MainTabBar() {
  const pathname = usePathname();

  return (
    <div className="border-b border-gray-200 bg-white/95 backdrop-blur supports-[backdrop-filter]:bg-white/80 dark:border-slate-800 dark:bg-slate-950/95 dark:supports-[backdrop-filter]:bg-slate-950/85">
      <div className="max-w-[1480px] mx-auto px-3 sm:px-6 lg:px-8 flex items-center gap-2">
        <nav
          className="flex flex-1 overflow-x-auto gap-1 sm:gap-2 py-2 -mx-1 scrollbar-hide"
          aria-label="메인 메뉴"
        >
          {TABS.map(({ href, label, shortLabel, icon: Icon }) => {
            const isActive =
              href === "/"
                ? pathname === "/"
                : pathname === href || pathname?.startsWith(`${href}/`);
            return (
              <Link
                key={href}
                href={href}
                className={`
                  flex items-center gap-1.5 sm:gap-2 shrink-0 rounded-full px-3 sm:px-4 py-2 text-sm font-medium transition whitespace-nowrap
                  ${
                    isActive
                      ? "bg-indigo-600 text-white shadow-sm"
                      : "text-gray-600 hover:text-indigo-600 hover:bg-indigo-50 dark:text-slate-300 dark:hover:text-indigo-400 dark:hover:bg-slate-800"
                  }
                `}
              >
                <Icon className="w-4 h-4 shrink-0" aria-hidden />
                <span className="hidden sm:inline">{label}</span>
                <span className="sm:hidden">{shortLabel}</span>
              </Link>
            );
          })}
        </nav>
        <div className="shrink-0">
          <ThemeToggle />
        </div>
      </div>
    </div>
  );
}
