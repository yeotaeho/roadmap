"use client";

import React, { useState } from "react";
import Link from "next/link";
import {
  Activity,
  BadgeCheck,
  Compass,
  Link2,
  MoveRight,
  Sparkles,
  Rocket,
  TrendingUp,
  Workflow,
} from "lucide-react";
import { CHANCE_OPPORTUNITIES } from "@/data/chanceOpportunities";
import { GAP_ISSUES } from "@/data/gapIssues";
import { PulseTab } from "./PulseTab";

const SUB_TABS = [
  {
    id: "pulse" as const,
    label: "펄스",
    fullLabel: "실시간 펄스",
    sub: "Pulse",
    icon: Activity,
  },
  {
    id: "gap" as const,
    label: "블루오션",
    fullLabel: "블루오션",
    sub: "The Gap",
    icon: Compass,
  },
  {
    id: "sync" as const,
    label: "싱크",
    fullLabel: "싱크로율",
    sub: "Sync",
    icon: Link2,
  },
  {
    id: "chance" as const,
    label: "찬스",
    fullLabel: "다이렉트 찬스",
    sub: "Chance",
    icon: Rocket,
  },
] as const;

type SubTabId = (typeof SUB_TABS)[number]["id"];

export function DashboardView() {
  const [sub, setSub] = useState<SubTabId>("pulse");

  return (
    <div className="space-y-7">
      <div>
        <h1 className="text-2xl sm:text-3xl font-bold text-slate-900 dark:text-slate-100">
          인사이트 대시보드
        </h1>
        <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
          지금의 흐름, 기회, 나와의 연결, 당장의 행동을 한곳에서 확인하세요.
        </p>
      </div>

      <div
        className="flex flex-wrap gap-2 p-1.5 bg-indigo-50/70 rounded-2xl border border-indigo-100 dark:bg-slate-900 dark:border-slate-700"
        role="tablist"
        aria-label="대시보드 세부 보기"
      >
        {SUB_TABS.map(({ id, label, fullLabel, icon: Icon }) => {
          const active = sub === id;
          return (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={active}
              onClick={() => setSub(id)}
              className={`
                flex items-center gap-2 rounded-xl px-3 sm:px-4 py-2.5 text-sm font-medium transition
                ${
                  active
                    ? "bg-white text-indigo-700 shadow-sm ring-1 ring-indigo-100 dark:bg-slate-800 dark:text-indigo-300 dark:ring-slate-700"
                    : "text-slate-600 hover:text-indigo-700 hover:bg-white/70 dark:text-slate-300 dark:hover:text-indigo-300 dark:hover:bg-slate-800/80"
                }
              `}
            >
              <Icon className="w-4 h-4 shrink-0" aria-hidden />
              <span className="hidden sm:inline">{fullLabel}</span>
              <span className="sm:hidden">{label}</span>
            </button>
          );
        })}
      </div>

      <div
        className="rounded-2xl border border-slate-200 bg-white p-4 sm:p-6 shadow-[0_8px_30px_rgba(15,23,42,0.08)] min-h-[420px] dark:border-slate-700 dark:bg-slate-900 dark:shadow-none"
        role="tabpanel"
      >
        {sub === "pulse" && <PulseTab />}
        {sub === "gap" && <GapPanel />}
        {sub === "sync" && <SyncPanel />}
        {sub === "chance" && <ChancePanel />}
      </div>

      <p className="text-center text-xs text-slate-500 dark:text-slate-400">
        백엔드 연동 전입니다. 수치·카드는 Mock입니다.
      </p>
    </div>
  );
}

function OpportunityRadar() {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-800">
      <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-100">기회 레이더 (Mock)</h3>
      <svg viewBox="0 0 260 180" className="w-full h-44 mt-3">
        <polygon points="130,20 220,75 190,155 70,155 40,75" fill="#eef2ff" />
        <polygon points="130,40 200,82 178,142 82,142 60,82" fill="#e0e7ff" />
        <polygon points="130,56 186,88 168,132 92,132 74,88" fill="#c7d2fe" />
        <polygon
          points="130,50 198,86 164,130 86,126 70,88"
          fill="rgba(16,185,129,0.35)"
          stroke="#10b981"
          strokeWidth="2"
        />
      </svg>
      <p className="text-xs text-slate-500 dark:text-slate-400">
        자본 유입 대비 인재 공급이 낮은 영역이 블루오션입니다.
      </p>
    </div>
  );
}

function GapPanel() {
  return (
    <div className="space-y-4">
      <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100">블루오션 (세상의 결핍)</h2>
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="space-y-3">
          {GAP_ISSUES.map((card) => (
            <article key={card.id} className="rounded-2xl overflow-hidden border border-slate-200 dark:border-slate-700">
              <div className="grid sm:grid-cols-2">
                <div className="bg-slate-900 text-white p-4">
                  <p className="text-xs text-slate-300">세상의 문제</p>
                  <p className="mt-2 text-sm font-medium">{card.problem}</p>
                </div>
                <div className="bg-emerald-50 p-4 border-t sm:border-t-0 sm:border-l border-emerald-100 dark:bg-emerald-900/20 dark:border-emerald-900/40">
                  <p className="text-xs text-emerald-700">청년의 기회</p>
                  <p className="mt-2 text-sm font-semibold text-emerald-900">{card.chance}</p>
                </div>
              </div>
              <div className="px-4 py-3 bg-white border-t border-slate-100 dark:bg-slate-900 dark:border-slate-700">
                <Link
                  href={`/dashboard/gap/issues/${card.id}`}
                  className="inline-flex items-center gap-1 text-sm font-medium text-indigo-600 hover:text-indigo-700"
                >
                  이 분야 파고들기 <MoveRight className="w-4 h-4" />
                </Link>
              </div>
            </article>
          ))}
        </div>
        <OpportunityRadar />
      </div>
    </div>
  );
}

function SyncRadar() {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-800">
      <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-100">나의 스탯 육각형</h3>
      <svg viewBox="0 0 260 180" className="w-full h-44 mt-3">
        <polygon points="130,20 220,70 220,130 130,160 40,130 40,70" fill="#f8fafc" />
        <polygon points="130,40 196,78 196,122 130,144 64,122 64,78" fill="#eef2ff" />
        <polygon
          points="130,52 186,86 178,122 130,136 82,120 74,88"
          fill="rgba(79,70,229,0.32)"
          stroke="#4f46e5"
          strokeWidth="2"
        />
        <polygon
          points="130,44 198,80 188,124 130,148 76,124 62,86"
          fill="rgba(16,185,129,0.2)"
          stroke="#10b981"
          strokeWidth="2"
          strokeDasharray="4 3"
        />
      </svg>
      <div className="mt-2 flex items-center gap-4 text-xs text-slate-600 dark:text-slate-400">
        <span className="inline-flex items-center gap-1">
          <span className="w-2.5 h-2.5 rounded-full bg-indigo-600" /> 내 역량
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="w-2.5 h-2.5 rounded-full bg-emerald-600" /> 목표 직무 요구치
        </span>
      </div>
    </div>
  );
}

function SyncPanel() {
  const growth = ["Python", "FastAPI", "LangGraph", "RAG", "AI 아키텍처"];
  const trendSync = [
    {
      trend: "지능형 기술 (AI & Data)",
      score: 86,
      delta: "+4",
      tags: ["LangGraph", "RAG", "FastAPI"],
      note: "관심 키워드와 시장 요구가 가장 잘 맞습니다.",
    },
    {
      trend: "지속 가능성 (Sustainability & ESG)",
      score: 62,
      delta: "+1",
      tags: ["ESG", "데이터 거버넌스"],
      note: "관심은 있으나 역량 신호는 아직 분산되어 있습니다.",
    },
    {
      trend: "미래 금융 (Future Finance)",
      score: 54,
      delta: "-2",
      tags: ["보안", "결제"],
      note: "트렌드는 강하지만 내 스택과의 교차점이 적습니다.",
    },
  ] as const;

  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-indigo-100 bg-indigo-50/50 p-4 flex items-start gap-3 dark:border-indigo-900/40 dark:bg-indigo-900/20">
        <Sparkles className="w-5 h-5 text-indigo-600 mt-0.5" />
        <p className="text-sm text-indigo-900 dark:text-indigo-200">
          태호님은 백엔드 기반이 탄탄해서 AI 아키텍처로 확장하기 좋은 타이밍입니다.
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <SyncRadar />
        <div className="rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-800">
          <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-100">성장 궤적</h3>
          <div className="mt-4 space-y-3">
            {growth.map((step, idx) => (
              <div key={step} className="flex items-center gap-2">
                <span className="w-6 h-6 rounded-full bg-indigo-100 text-indigo-700 text-xs font-semibold flex items-center justify-center dark:bg-indigo-900/40 dark:text-indigo-300">
                  {idx + 1}
                </span>
                <span className="text-sm text-slate-700 dark:text-slate-300">{step}</span>
                {idx < growth.length - 1 && (
                  <MoveRight className="w-4 h-4 text-slate-300 dark:text-slate-600" />
                )}
              </div>
            ))}
          </div>
          <p className="mt-4 text-xs text-slate-500 dark:text-slate-400">
            저장한 관심 키워드의 변화로 성장 흐름을 시각화합니다.
          </p>
        </div>
      </div>

      <section className="rounded-2xl border border-slate-200 bg-white p-4 sm:p-5 shadow-sm dark:border-slate-700 dark:bg-slate-800">
        <div className="flex items-center justify-between gap-2">
          <h3 className="text-sm font-semibold text-slate-800 inline-flex items-center gap-2 dark:text-slate-100">
            <TrendingUp className="w-4 h-4 text-indigo-600" aria-hidden />
            트렌드 대비 싱크로율
          </h3>
          <span className="text-[11px] text-slate-400 dark:text-slate-500">Mock · 전주 대비</span>
        </div>
        <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
          선택한 관심 키워드와 도메인별 시장 신호를 비교해 일치 정도를 보여줍니다.
        </p>
        <ul className="mt-4 space-y-3">
          {trendSync.map((row) => (
            <li
              key={row.trend}
              className="rounded-xl border border-slate-100 bg-slate-50/70 p-3 dark:border-slate-700 dark:bg-slate-900/50"
            >
              <div className="flex items-start justify-between gap-2">
                <p className="text-sm font-medium text-slate-800 leading-snug dark:text-slate-100">{row.trend}</p>
                <div className="shrink-0 text-right">
                  <p className="text-lg font-bold text-indigo-700">{row.score}</p>
                  <p
                    className={`text-[11px] font-semibold ${
                      row.delta.startsWith("-") ? "text-rose-600" : "text-emerald-600"
                    }`}
                  >
                    {row.delta}pt
                  </p>
                </div>
              </div>
              <div className="mt-2 h-2 rounded-full bg-slate-200 overflow-hidden dark:bg-slate-700">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-emerald-400"
                  style={{ width: `${row.score}%` }}
                />
              </div>
              <div className="mt-3 flex flex-wrap items-center gap-y-2 gap-x-1">
                {row.tags.map((tag, idx) => (
                  <React.Fragment key={`${row.trend}-${tag}`}>
                    <div className="flex items-center gap-2">
                      <span className="w-6 h-6 rounded-full bg-indigo-100 text-indigo-700 text-xs font-semibold flex items-center justify-center dark:bg-indigo-900/40 dark:text-indigo-300">
                        {idx + 1}
                      </span>
                      <span className="text-sm text-slate-700 dark:text-slate-300">{tag}</span>
                    </div>
                    {idx < row.tags.length - 1 && (
                      <MoveRight className="w-4 h-4 text-slate-300 dark:text-slate-600" aria-hidden />
                    )}
                  </React.Fragment>
                ))}
              </div>
              <p className="mt-2 text-xs text-slate-600 dark:text-slate-400">{row.note}</p>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

function ChancePanel() {
  return (
    <div className="space-y-4">
      <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100">다이렉트 찬스</h2>
      <div className="flex gap-3 overflow-x-auto pb-1 scrollbar-hide">
        {CHANCE_OPPORTUNITIES.map((item, idx) => (
          <article
            key={item.id}
            className={`min-w-[280px] max-w-[320px] rounded-2xl border bg-white p-4 shadow-sm dark:bg-slate-800 ${
              idx === 0
                ? "border-violet-200 shadow-[0_0_0_2px_rgba(139,92,246,0.15)] dark:border-violet-900/50"
                : "border-slate-200 dark:border-slate-700"
            }`}
          >
            <div className="flex items-start justify-between gap-2">
              <span className="text-xs font-semibold text-indigo-700 bg-indigo-50 px-2 py-1 rounded-full dark:bg-indigo-900/30 dark:text-indigo-300">
                {item.type}
              </span>
              <span className="text-xs font-bold text-emerald-700 bg-emerald-50 px-2 py-1 rounded-full inline-flex items-center gap-1 dark:bg-emerald-900/30 dark:text-emerald-300">
                <BadgeCheck className="w-3.5 h-3.5" />
                일치율 {item.match}%
              </span>
            </div>
            <p className="mt-3 text-sm font-semibold text-slate-900 dark:text-slate-100">{item.title}</p>
            <p className="mt-2 text-xs text-violet-700 font-bold dark:text-violet-300">{item.dday}</p>
            <div className="mt-4 flex items-center justify-between">
              <button
                type="button"
                className="text-xs font-medium text-slate-600 bg-slate-100 px-2.5 py-1 rounded-full dark:bg-slate-700 dark:text-slate-300"
              >
                저장
              </button>
              <Link
                href={`/dashboard/chance/opportunities/${item.id}`}
                className="text-xs font-medium text-indigo-600 hover:text-indigo-700 inline-flex items-center gap-1 dark:text-indigo-300 dark:hover:text-indigo-200"
              >
                자세히 보기 <MoveRight className="w-3.5 h-3.5" />
              </Link>
            </div>
          </article>
        ))}
      </div>
      <Link
        href="/coach"
        className="inline-flex text-sm font-medium text-indigo-600 hover:text-indigo-700 items-center gap-1 dark:text-indigo-300 dark:hover:text-indigo-200"
      >
        AI 코치에게 이 기회에 대해 물어보기 <Workflow className="w-4 h-4" />
      </Link>
    </div>
  );
}
