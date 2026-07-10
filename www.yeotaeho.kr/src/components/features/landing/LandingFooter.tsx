// 랜딩 전용 경량 푸터 — 앱 셸의 Footer와 별개
import Link from "next/link";
import { LANDING_COPY } from "./landing.copy";

export function LandingFooter() {
  return (
    <footer className="border-t border-slate-200 bg-white py-10 dark:border-slate-800 dark:bg-slate-950">
      <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 px-4 sm:flex-row sm:px-6 lg:px-8">
        <p className="text-sm text-slate-500 dark:text-slate-400">
          {LANDING_COPY.footer.copyright}
        </p>
        <nav className="flex items-center gap-6">
          {LANDING_COPY.footer.links.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="text-sm text-slate-500 transition-colors hover:text-slate-900 dark:text-slate-400 dark:hover:text-white"
            >
              {link.label}
            </Link>
          ))}
        </nav>
      </div>
    </footer>
  );
}
