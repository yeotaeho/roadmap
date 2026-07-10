// 랜딩 히어로 섹션 — 라인별 텍스트 리빌 + 배경 오브·펄스 라인 스크럽 패럴랙스
"use client";

import { useRef } from "react";
import Link from "next/link";
import { ChevronDown } from "lucide-react";
import { gsap, MM_CONDITIONS, useGSAP } from "../gsap";
import { LANDING_COPY } from "../landing.copy";

const { hero } = LANDING_COPY;

export function HeroSection() {
  const ref = useRef<HTMLElement>(null);

  useGSAP(
    () => {
      const mm = gsap.matchMedia();
      // reduced-motion에서는 아무 연출도 걸지 않음 — 콘텐츠는 기본 표시 상태
      mm.add(MM_CONDITIONS.motionOK, () => {
        // 진입 리빌 (1회)
        gsap
          .timeline({ defaults: { ease: "power3.out" } })
          .from(".hero-line-inner", { yPercent: 110, duration: 0.9, stagger: 0.12 })
          .from(".hero-eyebrow", { y: 16, opacity: 0, duration: 0.5 }, "<0.1")
          .from(".hero-sub", { y: 20, opacity: 0, duration: 0.6 }, "-=0.4")
          .from(".hero-cta", { y: 20, opacity: 0, duration: 0.6 }, "-=0.35")
          .from(".hero-scroll-hint", { opacity: 0, duration: 0.8 }, "-=0.2");

        // 배경 레이어 패럴랙스 + 콘텐츠 페이드아웃 (스크럽)
        const scrub = { trigger: ref.current, start: "top top", end: "bottom top", scrub: true } as const;
        gsap.to(".hero-orb-a", { yPercent: 30, scrollTrigger: scrub });
        gsap.to(".hero-orb-b", { yPercent: 55, scrollTrigger: scrub });
        gsap.to(".hero-pulse-svg", { yPercent: 18, scrollTrigger: scrub });
        gsap.to(".hero-content", { opacity: 0, yPercent: -12, ease: "none", scrollTrigger: scrub });
      });

      // 마우스 좌표 추종 패럴랙스 — 데스크톱(포인터 환경) 한정.
      // 스크롤 패럴랙스(yPercent)와 다른 축(x/y 픽셀)이라 서로 간섭 없음.
      mm.add(`${MM_CONDITIONS.isDesktop} and ${MM_CONDITIONS.motionOK}`, () => {
        const section = ref.current;
        if (!section) return;

        // depth 부호를 섞어 레이어마다 반대 방향으로 움직여 깊이감을 만든다
        const layers: { x: (v: number) => void; y: (v: number) => void; depth: number }[] = [];
        (
          [
            [".hero-orb-a", 44],
            [".hero-orb-b", -64],
            [".hero-pulse-svg", 20],
            [".hero-content", -14],
          ] as const
        ).forEach(([sel, depth]) => {
          const el = section.querySelector(sel);
          if (!el) return;
          layers.push({
            x: gsap.quickTo(el, "x", { duration: 0.8, ease: "power3.out" }),
            y: gsap.quickTo(el, "y", { duration: 0.8, ease: "power3.out" }),
            depth,
          });
        });

        const onMove = (e: PointerEvent) => {
          const nx = e.clientX / window.innerWidth - 0.5; // -0.5 ~ 0.5
          const ny = e.clientY / window.innerHeight - 0.5;
          layers.forEach((l) => {
            l.x(nx * 2 * l.depth);
            l.y(ny * 2 * l.depth);
          });
        };
        const onLeave = () => layers.forEach((l) => (l.x(0), l.y(0)));

        section.addEventListener("pointermove", onMove);
        section.addEventListener("pointerleave", onLeave);
        return () => {
          section.removeEventListener("pointermove", onMove);
          section.removeEventListener("pointerleave", onLeave);
        };
      });

      return () => mm.revert(); // unmount 시 media query 리스너까지 확실히 해제
    },
    { scope: ref }
  );

  return (
    <section
      ref={ref}
      className="relative flex min-h-screen items-center justify-center overflow-hidden bg-white dark:bg-slate-950"
    >
      {/* 배경 그라디언트 오브 */}
      <div className="hero-orb-a pointer-events-none absolute -left-32 top-[-10%] h-[28rem] w-[28rem] rounded-full bg-indigo-400/20 blur-3xl dark:bg-indigo-500/15" />
      <div className="hero-orb-b pointer-events-none absolute -right-24 bottom-[-15%] h-[24rem] w-[24rem] rounded-full bg-sky-300/20 blur-3xl dark:bg-sky-500/10" />

      {/* 배경 펄스 라인 */}
      <svg
        viewBox="0 0 1200 400"
        preserveAspectRatio="none"
        className="hero-pulse-svg pointer-events-none absolute inset-x-0 bottom-0 h-[45%] w-full opacity-40 dark:opacity-25"
        aria-hidden
      >
        <path
          d="M0 300 L160 260 L300 290 L460 190 L620 230 L800 120 L980 170 L1200 90"
          fill="none"
          pathLength={1}
          className="landing-viz-draw stroke-indigo-400"
          strokeWidth={2.5}
        />
        <path
          d="M0 350 L200 330 L380 345 L560 280 L760 310 L960 240 L1200 270"
          fill="none"
          pathLength={1}
          className="landing-viz-draw stroke-slate-300 dark:stroke-slate-700"
          strokeWidth={2}
          style={{ animationDelay: "0.4s" }}
        />
      </svg>

      <div className="hero-content relative z-10 mx-auto max-w-4xl px-4 text-center sm:px-6">
        <p className="hero-eyebrow mb-5 inline-block rounded-full border border-indigo-200 bg-indigo-50 px-4 py-1.5 text-sm font-semibold text-indigo-600 dark:border-indigo-900/60 dark:bg-indigo-950/40 dark:text-indigo-300">
          {hero.eyebrow}
        </p>
        <h1 className="text-4xl font-extrabold leading-[1.15] tracking-tight text-slate-900 dark:text-white sm:text-6xl lg:text-7xl">
          {hero.titleLines.map((line) => (
            <span key={line} className="hero-line block overflow-hidden">
              <span className="hero-line-inner block">{line}</span>
            </span>
          ))}
        </h1>
        <p className="hero-sub mx-auto mt-6 max-w-2xl text-base leading-relaxed text-slate-600 dark:text-slate-300 sm:text-lg">
          {hero.subtitle}
        </p>
        <div className="hero-cta mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
          <Link
            href={hero.primaryCta.href}
            className="w-full rounded-full bg-indigo-600 px-8 py-3.5 text-base font-semibold text-white shadow-lg shadow-indigo-600/25 transition-colors hover:bg-indigo-500 sm:w-auto"
          >
            {hero.primaryCta.label}
          </Link>
          <Link
            href={hero.secondaryCta.href}
            className="w-full rounded-full border border-slate-300 px-8 py-3.5 text-base font-semibold text-slate-700 transition-colors hover:border-slate-400 hover:text-slate-950 dark:border-slate-700 dark:text-slate-300 dark:hover:border-slate-500 dark:hover:text-white sm:w-auto"
          >
            {hero.secondaryCta.label}
          </Link>
        </div>
      </div>

      <div className="hero-scroll-hint absolute bottom-8 left-1/2 z-10 -translate-x-1/2 text-center">
        <p className="mb-1 text-xs font-medium text-slate-400 dark:text-slate-500">{hero.scrollHint}</p>
        <ChevronDown aria-hidden className="landing-viz-float mx-auto h-5 w-5 text-slate-400 dark:text-slate-500" />
      </div>
    </section>
  );
}
