// 대시보드 패널 로딩/에러/빈데이터 상태 표시 (mock 폴백 없음 — 실데이터 아니면 에러)
"use client";

import React from "react";
import { AlertCircle } from "lucide-react";

export function PanelStatus({
  isLoading,
  isError,
  isEmpty,
  label,
  children,
}: {
  isLoading: boolean;
  isError: boolean;
  isEmpty: boolean;
  label: string;
  children: React.ReactNode;
}) {
  if (isLoading) {
    return (
      <div className="rounded-xl border border-slate-200 bg-slate-50 p-6 text-center text-sm text-slate-500 dark:border-slate-700 dark:bg-slate-900/50 dark:text-slate-400">
        {label} 불러오는 중…
      </div>
    );
  }
  if (isError || isEmpty) {
    return (
      <div className="rounded-xl border border-rose-200 bg-rose-50 p-6 text-center dark:border-rose-900/50 dark:bg-rose-900/20">
        <AlertCircle className="mx-auto mb-2 h-5 w-5 text-rose-500" aria-hidden />
        <p className="text-sm font-medium text-rose-700 dark:text-rose-300">
          {isError
            ? `${label} 데이터를 불러오지 못했습니다.`
            : `${label} 실데이터가 아직 없습니다.`}
        </p>
        <p className="mt-1 text-xs text-rose-500 dark:text-rose-400">
          백엔드 정제 파이프라인 실행 후 다시 시도해 주세요.
        </p>
      </div>
    );
  }
  return <>{children}</>;
}
