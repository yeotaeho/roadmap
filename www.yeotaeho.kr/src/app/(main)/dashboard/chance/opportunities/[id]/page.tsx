"use client";

import Link from "next/link";
import { useParams } from "next/navigation";

import { PanelStatus } from "@/components/features/dashboard/PanelStatus";
import { ddayLabel } from "@/lib/api/dashboard";
import { useOpportunityDetail } from "@/hooks/useDashboard";

export default function ChanceOpportunityDetailPage() {
  const params = useParams();
  const id = String(params?.id ?? "");
  const { data: opp, isLoading, isError } = useOpportunityDetail(id);

  return (
    <div className="space-y-6">
      <p className="text-xs font-semibold text-indigo-600">다이렉트 찬스 · 기회 상세</p>

      <PanelStatus isLoading={isLoading} isError={isError} isEmpty={!opp} label="공고">
        {opp && (
          <div className="space-y-6">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h1 className="text-2xl sm:text-3xl font-bold text-slate-900 dark:text-slate-100">{opp.title}</h1>
                {opp.brief_description && (
                  <p className="mt-2 text-sm text-slate-600 max-w-3xl dark:text-slate-400">{opp.brief_description}</p>
                )}
                {opp.host_name && (
                  <p className="mt-1 text-xs text-slate-500 dark:text-slate-500">{opp.host_name}</p>
                )}
              </div>
              <div className="flex flex-col items-end gap-2">
                {opp.opportunity_type && (
                  <span className="text-xs font-semibold text-indigo-700 bg-indigo-50 px-2.5 py-1 rounded-full dark:bg-indigo-900/30 dark:text-indigo-300">
                    {opp.opportunity_type}
                  </span>
                )}
                <span className="text-xs font-bold text-violet-700 dark:text-violet-300">
                  {ddayLabel(opp.d_day_date)}
                </span>
              </div>
            </div>

            <div className="grid gap-4 lg:grid-cols-2">
              <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-800">
                <h2 className="text-sm font-semibold text-slate-800 dark:text-slate-100">지원/참가 자격</h2>
                {opp.eligibility_checks.length > 0 ? (
                  <ul className="mt-3 space-y-2 text-sm text-slate-700 list-disc pl-5 dark:text-slate-300">
                    {opp.eligibility_checks.map((t) => (
                      <li key={t}>{t}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="mt-3 text-sm text-slate-500 dark:text-slate-400">공고문에서 확인하세요.</p>
                )}
              </section>
              <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-800">
                <h2 className="text-sm font-semibold text-slate-800 dark:text-slate-100">대상 / 혜택</h2>
                <div className="mt-3 space-y-2 text-sm text-slate-700 dark:text-slate-300">
                  {opp.target_audience && <p>대상: {opp.target_audience}</p>}
                  {opp.benefit_summary && <p>혜택: {opp.benefit_summary}</p>}
                  {!opp.target_audience && !opp.benefit_summary && (
                    <p className="text-slate-500 dark:text-slate-400">공고문에서 확인하세요.</p>
                  )}
                </div>
              </section>
            </div>

            {opp.reference_links.length > 0 && (
              <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-800">
                <h2 className="text-sm font-semibold text-slate-800 dark:text-slate-100">관련 링크</h2>
                <ul className="mt-3 space-y-2">
                  {opp.reference_links.map((href, idx) => (
                    <li key={`${href}-${idx}`}>
                      <a
                        href={href}
                        className="text-sm font-semibold text-indigo-600 hover:text-indigo-700 underline underline-offset-2 break-all dark:text-indigo-300"
                        target="_blank"
                        rel="noreferrer"
                      >
                        {href}
                      </a>
                    </li>
                  ))}
                </ul>
              </section>
            )}
          </div>
        )}
      </PanelStatus>

      <div className="flex flex-wrap gap-3">
        <Link
          href="/coach"
          className="inline-flex items-center justify-center rounded-xl bg-indigo-600 text-white text-sm font-semibold px-4 py-2.5 hover:bg-indigo-700 transition"
        >
          AI 코치에게 이 기회 물어보기
        </Link>
        <Link
          href="/"
          className="inline-flex items-center justify-center rounded-xl border border-slate-200 bg-white text-sm font-semibold px-4 py-2.5 text-slate-700 hover:bg-slate-50 transition dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800"
        >
          대시보드로
        </Link>
      </div>
    </div>
  );
}
