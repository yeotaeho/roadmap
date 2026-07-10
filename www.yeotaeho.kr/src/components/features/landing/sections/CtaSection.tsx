// 랜딩 마지막 CTA 섹션 — 타이틀 스케일 리빌 + 배경 글로우 확산 스크럽
"use client";

import { useRef } from "react";
import Link from "next/link";
import { gsap, MM_CONDITIONS, useGSAP } from "../gsap";
import { LANDING_COPY } from "../landing.copy";

const { cta } = LANDING_COPY;

export function CtaSection() {
  const ref = useRef<HTMLElement>(null);

  useGSAP(
    () => {
      const mm = gsap.matchMedia();
      mm.add(MM_CONDITIONS.motionOK, () => {
        const scrub = {
          trigger: ref.current,
          start: "top 90%",
          end: "center center",
          scrub: 0.5,
        } as const;
        gsap.fromTo(".cta-content", { scale: 0.9, opacity: 0.4 }, { scale: 1, opacity: 1, ease: "none", scrollTrigger: scrub });
        gsap.fromTo(".cta-glow", { scale: 0.5, opacity: 0.2 }, { scale: 1.4, opacity: 1, ease: "none", scrollTrigger: scrub });
      });
    },
    { scope: ref }
  );

  return (
    <section
      ref={ref}
      className="relative overflow-hidden bg-slate-950 py-32 text-center sm:py-40"
    >
      <div className="cta-glow pointer-events-none absolute left-1/2 top-1/2 h-[30rem] w-[30rem] -translate-x-1/2 -translate-y-1/2 rounded-full bg-indigo-600/30 blur-3xl" />
      <div className="cta-content relative z-10 mx-auto max-w-3xl px-4 sm:px-6">
        <h2 className="text-3xl font-extrabold tracking-tight text-white sm:text-5xl">
          {cta.title}
        </h2>
        <p className="mt-4 text-base text-slate-300 sm:text-lg">{cta.subtitle}</p>
        <Link
          href={cta.button.href}
          className="mt-9 inline-block rounded-full bg-indigo-500 px-10 py-4 text-base font-semibold text-white shadow-lg shadow-indigo-500/30 transition-colors hover:bg-indigo-400"
        >
          {cta.button.label}
        </Link>
      </div>
    </section>
  );
}
