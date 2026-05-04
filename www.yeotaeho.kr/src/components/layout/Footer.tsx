import React from "react";

export const Footer: React.FC = () => {
  return (
    <footer className="bg-gray-100 mt-auto py-8 border-t border-gray-200 dark:bg-slate-900 dark:border-slate-800">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
          <div className="text-base font-extrabold text-gray-800 dark:text-slate-100">청년 인사이트</div>
          <div className="flex flex-wrap gap-3 text-sm text-gray-600 dark:text-slate-400">
            <a href="#" className="hover:text-indigo-600 dark:hover:text-indigo-400">
              이용약관
            </a>
            <a href="#" className="hover:text-indigo-600 font-semibold dark:hover:text-indigo-400">
              개인정보처리방침
            </a>
          </div>
        </div>
        <p className="mt-4 text-xs text-gray-500 dark:text-slate-500">
          © {new Date().getFullYear()} Youth Insight. All rights reserved.
        </p>
      </div>
    </footer>
  );
};
