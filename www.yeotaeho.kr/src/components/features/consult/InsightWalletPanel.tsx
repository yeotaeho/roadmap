"use client";

import { Copy, Target, Trash2, Wallet } from "lucide-react";
import type { CoachWalletItem } from "@/data/coachContext";

type Props = {
  activeFocusTitle: string;
  activeFocusSubtitle: string;
  activeFocusBody: string;
  activeTags: string[];
  wallet: CoachWalletItem[];
  onCopy: (id: string) => void;
  onRemove: (id: string) => void;
};

export function InsightWalletPanel({
  activeFocusTitle,
  activeFocusSubtitle,
  activeFocusBody,
  activeTags,
  wallet,
  onCopy,
  onRemove,
}: Props) {
  return (
    <div className="flex h-full min-h-0 flex-col gap-4">
      <section className="rounded-2xl border border-indigo-100 bg-white p-4 shadow-sm dark:border-indigo-900/40 dark:bg-slate-800">
        <p className="text-[11px] font-semibold uppercase tracking-wide text-indigo-600">
          Active Context
        </p>
        <div className="mt-2 flex items-start gap-2">
          <div className="rounded-lg bg-indigo-50 p-2 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-300">
            <Target className="h-4 w-4" />
          </div>
          <div>
            <p className="text-xs font-semibold text-slate-500 dark:text-slate-500">{activeFocusTitle}</p>
            <p className="mt-0.5 text-sm font-bold text-slate-900 dark:text-slate-100">{activeFocusSubtitle}</p>
            <p className="mt-2 text-xs leading-relaxed text-slate-600 dark:text-slate-400">{activeFocusBody}</p>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {activeTags.map((t) => (
                <span
                  key={t}
                  className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-700 dark:bg-slate-700 dark:text-slate-300"
                >
                  {t}
                </span>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="flex min-h-0 flex-1 flex-col rounded-2xl border border-slate-200 bg-[#F8FAFC] p-4 shadow-sm dark:border-slate-700 dark:bg-slate-900">
        <div className="mb-2 flex items-center gap-2">
          <Wallet className="h-4 w-4 text-indigo-600" />
          <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">Insight Wallet</h3>
        </div>
        <p className="text-xs text-slate-600 dark:text-slate-400">
          대화 중 저장한 문장·코드를 모아 두었다가 로드맵 아카이브에 옮기기 좋습니다.
        </p>
        <div className="mt-3 flex-1 space-y-2 overflow-y-auto pr-1">
          {wallet.length === 0 ? (
            <p className="rounded-xl border border-dashed border-slate-200 bg-white/80 px-3 py-6 text-center text-xs text-slate-500 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-500">
              AI 메시지 우측 하단의 지갑 아이콘으로 저장해 보세요.
            </p>
          ) : (
            wallet.map((item) => (
              <article
                key={item.id}
                className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm dark:border-slate-700 dark:bg-slate-800"
              >
                <p className="text-xs font-semibold text-slate-900 dark:text-slate-100">{item.title}</p>
                <pre className="mt-2 max-h-32 overflow-x-auto overflow-y-auto whitespace-pre-wrap rounded-lg bg-slate-50 p-2 font-mono text-[11px] leading-relaxed text-slate-800 ring-1 ring-slate-100 dark:bg-slate-900 dark:text-slate-200 dark:ring-slate-700">
                  {item.body}
                </pre>
                <div className="mt-2 flex justify-end gap-1">
                  <button
                    type="button"
                    onClick={() => onCopy(item.id)}
                    className="rounded-lg border border-slate-200 p-1.5 text-slate-600 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-900"
                    aria-label="복사"
                  >
                    <Copy className="h-3.5 w-3.5" />
                  </button>
                  <button
                    type="button"
                    onClick={() => onRemove(item.id)}
                    className="rounded-lg border border-slate-200 p-1.5 text-slate-600 hover:bg-indigo-50 hover:text-indigo-700 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-indigo-900/30 dark:hover:text-indigo-300"
                    aria-label="삭제"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              </article>
            ))
          )}
        </div>
      </section>
    </div>
  );
}
