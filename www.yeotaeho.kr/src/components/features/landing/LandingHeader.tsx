// 랜딩 상단 고정 헤더 — 스크롤 시 투명 배경에서 블러 배경으로 전환
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { LANDING_COPY } from "./landing.copy";

export function LandingHeader() {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 40);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header
      className={`landing-header fixed inset-x-0 top-0 z-50 transition-colors duration-300 ${
        scrolled ? "landing-header--scrolled" : ""
      }`}
    >
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6 lg:px-8">
        <Link href="/" className="flex items-baseline gap-2">
          <span className="text-lg font-extrabold tracking-tight text-slate-900 dark:text-white">
            {LANDING_COPY.brand.name}
          </span>
          <span className="hidden text-xs font-medium text-slate-500 dark:text-slate-400 sm:inline">
            {LANDING_COPY.brand.sub}
          </span>
        </Link>
        <nav className="flex items-center gap-2">
          <Link
            href={LANDING_COPY.header.login.href}
            className="rounded-full px-4 py-2 text-sm font-medium text-slate-700 transition-colors hover:text-slate-950 dark:text-slate-300 dark:hover:text-white"
          >
            {LANDING_COPY.header.login.label}
          </Link>
          <Link
            href={LANDING_COPY.header.start.href}
            className="rounded-full bg-indigo-600 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-indigo-500"
          >
            {LANDING_COPY.header.start.label}
          </Link>
        </nav>
      </div>
    </header>
  );
}
