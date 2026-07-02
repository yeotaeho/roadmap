"use client";

import Link from "next/link";
import { ChevronRight, Map } from "lucide-react";

export default function CoachPage() {
  return (
    <div className="mx-auto max-w-xl px-4 py-16 text-center">
      <div className="mx-auto mb-5 inline-flex rounded-2xl bg-indigo-100 p-4 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-300">
        <Map className="h-8 w-8" />
      </div>
      <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">로드맵 코치 준비 중</h1>
      <p className="mt-3 text-sm leading-relaxed text-slate-600 dark:text-slate-400">
        AI 코치는 상담실에서 발견한 방향을 바탕으로 성장 로드맵을 함께 설계합니다. 곧 찾아옵니다.
      </p>
      <Link
        href="/roadmap"
        className="mt-6 inline-flex items-center gap-1 rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-indigo-700"
      >
        지금은 로드맵 보기 <ChevronRight className="h-4 w-4" />
      </Link>
    </div>
  );
}
