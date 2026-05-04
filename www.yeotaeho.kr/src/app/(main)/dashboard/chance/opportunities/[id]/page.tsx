import Link from "next/link";
import { notFound } from "next/navigation";
import { getAllChanceOpportunityIds, getChanceOpportunityDetail } from "@/data/chanceOpportunities";

export function generateStaticParams() {
  return getAllChanceOpportunityIds().map((id) => ({ id }));
}

export default async function ChanceOpportunityDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const opp = getChanceOpportunityDetail(id);
  if (!opp) notFound();

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold text-indigo-600">다이렉트 찬스 · 기회 상세</p>
          <h1 className="mt-1 text-2xl sm:text-3xl font-bold text-slate-900 dark:text-slate-100">{opp.title}</h1>
          <p className="mt-2 text-sm text-slate-600 max-w-3xl dark:text-slate-400">{opp.summary}</p>
        </div>
        <div className="flex flex-col items-end gap-2">
          <span className="text-xs font-semibold text-indigo-700 bg-indigo-50 px-2.5 py-1 rounded-full dark:bg-indigo-900/30 dark:text-indigo-300">
            {opp.type}
          </span>
          <span className="text-xs font-bold text-emerald-700 bg-emerald-50 px-2.5 py-1 rounded-full dark:bg-emerald-900/30 dark:text-emerald-300">
            일치율 {opp.match}%
          </span>
          <span className="text-xs font-bold text-violet-700 dark:text-violet-300">{opp.dday}</span>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-800">
          <h2 className="text-sm font-semibold text-slate-800 dark:text-slate-100">지원/참가 자격(체크)</h2>
          <ul className="mt-3 space-y-2 text-sm text-slate-700 list-disc pl-5 dark:text-slate-300">
            {opp.eligibility.map((t) => (
              <li key={t}>{t}</li>
            ))}
          </ul>
        </section>
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-800">
          <h2 className="text-sm font-semibold text-slate-800 dark:text-slate-100">준비물(바로 실행)</h2>
          <ol className="mt-3 space-y-2 text-sm text-slate-700 list-decimal pl-5 dark:text-slate-300">
            {opp.prepare.map((t) => (
              <li key={t}>{t}</li>
            ))}
          </ol>
        </section>
      </div>

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-800">
        <h2 className="text-sm font-semibold text-slate-800 dark:text-slate-100">관련 링크(예시)</h2>
        <ul className="mt-3 space-y-2">
          {opp.links.map((l, idx) => (
            <li key={`${l.label}-${idx}`}>
              <a
                href={l.href}
                className="text-sm font-semibold text-indigo-600 hover:text-indigo-700 underline underline-offset-2 dark:text-indigo-300 dark:hover:text-indigo-200"
                target="_blank"
                rel="noreferrer"
              >
                {l.label}
              </a>
            </li>
          ))}
        </ul>
      </section>

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

      <p className="text-xs text-slate-500 dark:text-slate-500">
        외부 링크는 실제 공고로 교체하세요. 지금은 placeholder(`example.com`)입니다.
      </p>
    </div>
  );
}
