import Link from "next/link";
import { notFound } from "next/navigation";
import { getAllGapIssueIds, getGapIssueDetail } from "@/data/gapIssues";

export function generateStaticParams() {
  return getAllGapIssueIds().map((id) => ({ id }));
}

export default async function GapIssueDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const issue = getGapIssueDetail(id);
  if (!issue) notFound();

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs font-semibold text-indigo-600">블루오션 · 이슈 상세</p>
        <h1 className="mt-1 text-2xl sm:text-3xl font-bold text-slate-900 dark:text-slate-100">이슈 상세</h1>
        <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">카드에서 선택한 결핍/기회를 확장해 설명합니다.</p>
      </div>

      <article className="rounded-2xl overflow-hidden border border-slate-200 shadow-sm dark:border-slate-700">
        <div className="grid sm:grid-cols-2">
          <div className="bg-slate-900 text-white p-5">
            <p className="text-xs text-slate-300">세상의 문제</p>
            <p className="mt-2 text-base font-semibold leading-relaxed">{issue.problem}</p>
          </div>
          <div className="bg-emerald-50 p-5 border-t sm:border-t-0 sm:border-l border-emerald-100 dark:bg-emerald-900/20 dark:border-emerald-900/40">
            <p className="text-xs text-emerald-700 dark:text-emerald-300">청년의 기회</p>
            <p className="mt-2 text-base font-semibold text-emerald-950 leading-relaxed dark:text-emerald-200">{issue.chance}</p>
          </div>
        </div>
      </article>

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-800">
        <h2 className="text-sm font-semibold text-slate-800 dark:text-slate-100">요약</h2>
        <p className="mt-3 text-sm text-slate-700 leading-relaxed dark:text-slate-300">{issue.summary}</p>
      </section>

      <div className="grid gap-4 lg:grid-cols-2">
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-800">
          <h2 className="text-sm font-semibold text-slate-800 dark:text-slate-100">이해관계자(참고)</h2>
          <ul className="mt-3 space-y-2 text-sm text-slate-700 list-disc pl-5 dark:text-slate-300">
            {issue.stakeholders.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
        </section>
        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-800">
          <h2 className="text-sm font-semibold text-slate-800 dark:text-slate-100">다음 액션(실행)</h2>
          <ol className="mt-3 space-y-2 text-sm text-slate-700 list-decimal pl-5 dark:text-slate-300">
            {issue.nextSteps.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ol>
        </section>
      </div>

      <div className="flex flex-wrap gap-3">
        <Link
          href="/coach"
          className="inline-flex items-center justify-center rounded-xl bg-indigo-600 text-white text-sm font-semibold px-4 py-2.5 hover:bg-indigo-700 transition"
        >
          AI 코치에게 이 이슈 물어보기
        </Link>
        <Link
          href="/"
          className="inline-flex items-center justify-center rounded-xl border border-slate-200 bg-white text-sm font-semibold px-4 py-2.5 text-slate-700 hover:bg-slate-50 transition dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800"
        >
          대시보드로
        </Link>
      </div>

      <p className="text-xs text-slate-500 dark:text-slate-500">
        본 페이지는 Mock 기준 템플릿입니다. 이후 `issueId`로 DB/RAG 근거를 붙입니다.
      </p>
    </div>
  );
}
