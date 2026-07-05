"use client";

// 대시보드 앱-셸 왼쪽 full-height 사이드바 — 탭·펄스 세부 섹션 네비게이션.

import React from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";
import { SideNav } from "@/components/layout/SideNav";
import { SUB_TABS, PULSE_SECTIONS, useDashboardNav } from "./DashboardNavContext";

// 펄스 탭의 접이식 하위 섹션 때문에 SideNavButton 대신 버튼을 직접 렌더하되,
// 컨테이너(aside/nav)는 공유 SideNav로 통일해 스타일 단일 소스를 유지한다.
export function DashboardSidebar() {
  const { activeTab, setActiveTab, pulseSection, setPulseSection, pulseOpen, setPulseOpen } =
    useDashboardNav();

  return (
    <SideNav>
        {SUB_TABS.map(({ id, fullLabel, icon: Icon }) => {
          const isActive = activeTab === id;
          const isPulse = id === "pulse";
          return (
            <React.Fragment key={id}>
              <button
                type="button"
                onClick={() => {
                  if (isPulse) {
                    setActiveTab("pulse");
                    setPulseOpen((open) => !open);
                  } else {
                    setActiveTab(id);
                  }
                }}
                aria-current={isActive ? "page" : undefined}
                aria-expanded={isPulse ? pulseOpen : undefined}
                className={cn(
                  "flex items-center gap-2.5 rounded-lg px-3 py-2.5 text-sm transition text-left",
                  isActive
                    ? "bg-white font-semibold text-indigo-700 shadow-sm ring-1 ring-indigo-100 dark:bg-slate-800 dark:text-indigo-300 dark:ring-slate-700"
                    : "font-medium text-slate-600 hover:bg-white/70 hover:text-indigo-700 dark:text-slate-300 dark:hover:bg-slate-800/80 dark:hover:text-indigo-300"
                )}
              >
                <Icon className="w-4 h-4 shrink-0" aria-hidden />
                <span className="flex-1">{fullLabel}</span>
                {isPulse && (
                  <ChevronDown
                    className={cn(
                      "w-4 h-4 shrink-0 text-slate-400 transition-transform",
                      pulseOpen && "rotate-180"
                    )}
                    aria-hidden
                  />
                )}
              </button>
              {isPulse && pulseOpen && (
                <div className="mb-1 ml-4 flex flex-col gap-0.5 border-l border-indigo-200 pl-2 dark:border-slate-700">
                  {PULSE_SECTIONS.map((s) => (
                    <button
                      key={s.id}
                      type="button"
                      onClick={() => {
                        setActiveTab("pulse");
                        setPulseSection(s.id);
                      }}
                      aria-current={pulseSection === s.id ? "page" : undefined}
                      className={cn(
                        "rounded-md px-3 py-1.5 text-[13px] text-left transition",
                        pulseSection === s.id
                          ? "bg-white font-medium text-indigo-700 shadow-sm dark:bg-slate-800 dark:text-indigo-300"
                          : "text-slate-500 hover:text-indigo-700 hover:bg-white/60 dark:text-slate-400 dark:hover:text-indigo-300 dark:hover:bg-slate-800/60"
                      )}
                    >
                      {s.label}
                    </button>
                  ))}
                </div>
              )}
            </React.Fragment>
          );
        })}
    </SideNav>
  );
}
