import Link from "next/link";
import { notFound } from "next/navigation";
import { getAllPulseSectorSlugs, getPulseSectorBundle } from "@/data/pulseSectors";

export function generateStaticParams() {
  return getAllPulseSectorSlugs().map((slug) => ({ slug }));
}

export default async function PulseSectorDetailPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const bundle = getPulseSectorBundle(slug);
  if (!bundle) notFound();

  const { sector, detail } = bundle;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs font-semibold text-indigo-600">실시간 펄스 · 도메인 상세</p>
          <h1 className="mt-1 text-2xl sm:text-3xl font-bold text-slate-900 dark:text-slate-100">{sector.title}</h1>
          <p className="mt-2 text-sm text-slate-600 max-w-3xl dark:text-slate-400">{detail.headline}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <span
            className={`text-xs px-2.5 py-1 rounded-full font-semibold ${sector.badgeInfo}`}
          >
            {sector.status}
          </span>
          <span className="text-xs px-2.5 py-1 rounded-full bg-slate-100 text-slate-700 font-semibold dark:bg-slate-800 dark:text-slate-300">
            점수 {sector.score}
          </span>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <section className="lg:col-span-2 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-800">
          <h2 className="text-sm font-semibold text-slate-800 dark:text-slate-100">왜 지금 중요한가</h2>
          <ul className="mt-3 space-y-2 text-sm text-slate-700 list-disc pl-5 dark:text-slate-300">
            {detail.whyItMatters.map((t) => (
              <li key={t}>{t}</li>
            ))}
          </ul>
        </section>

        <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-800">
          <h2 className="text-sm font-semibold text-slate-800 dark:text-slate-100">핵심 신호(요약)</h2>
          <dl className="mt-3 space-y-3">
            {detail.signals.map((s) => (
              <div key={s.label} className="rounded-xl border border-slate-100 bg-slate-50/70 p-3 dark:border-slate-700 dark:bg-slate-900/60">
                <dt className="text-[11px] font-semibold text-slate-500 dark:text-slate-500">{s.label}</dt>
                <dd className="mt-1 text-sm font-medium text-slate-900 dark:text-slate-100">{s.value}</dd>
              </div>
            ))}
          </dl>
        </section>
      </div>

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-800">
        <h2 className="text-sm font-semibold text-slate-800 dark:text-slate-100">리스크 / 주의점</h2>
        <ul className="mt-3 space-y-2 text-sm text-slate-700 list-disc pl-5 dark:text-slate-300">
          {detail.risks.map((t) => (
            <li key={t}>{t}</li>
          ))}
        </ul>
      </section>

      <div className="flex flex-wrap gap-3">
        {detail.actions.map((a) => (
          <Link
            key={a.href + a.label}
            href={a.href}
            className="inline-flex items-center justify-center rounded-xl bg-indigo-600 text-white text-sm font-semibold px-4 py-2.5 hover:bg-indigo-700 transition"
          >
            {a.label}
          </Link>
        ))}
        <Link
          href="/"
          className="inline-flex items-center justify-center rounded-xl border border-slate-200 bg-white text-sm font-semibold px-4 py-2.5 text-slate-700 hover:bg-slate-50 transition dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800"
        >
          대시보드로
        </Link>
      </div>

      <p className="text-xs text-slate-500 dark:text-slate-500">
        본 페이지는 Mock 기준 템플릿입니다. 백엔드 연동 후 `slug` 기준으로 실데이터를 주입합니다.
      </p>
    </div>
  );
}
