// 랜딩 3단계 안내 섹션 — 연결선 드로잉 스크럽 + 스텝 카드 순차 리빌
"use client";

import { useRef } from "react";
import { gsap, MM_CONDITIONS, useGSAP } from "../gsap";
import { LANDING_COPY } from "../landing.copy";

const { howItWorks } = LANDING_COPY;

export function HowItWorksSection() {
  const ref = useRef<HTMLElement>(null);

  useGSAP(
    () => {
      const mm = gsap.matchMedia();
      mm.add(MM_CONDITIONS.motionOK, () => {
        gsap.fromTo(
          ".hiw-line",
          { strokeDashoffset: 1 },
          {
            strokeDashoffset: 0,
            ease: "none",
            scrollTrigger: {
              trigger: ref.current,
              start: "top 70%",
              end: "bottom 60%",
              scrub: 0.5,
            },
          }
        );
        gsap.from(".hiw-step", {
          y: 32,
          opacity: 0,
          duration: 0.7,
          stagger: 0.15,
          ease: "power3.out",
          scrollTrigger: { trigger: ref.current, start: "top 70%", once: true },
        });
      });
    },
    { scope: ref }
  );

  return (
    <section ref={ref} className="bg-white py-24 dark:bg-slate-950 sm:py-32">
      <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
        <h2 className="mb-16 text-center text-3xl font-extrabold tracking-tight text-slate-900 dark:text-white sm:text-4xl">
          {howItWorks.title}
        </h2>
        <div className="relative">
          {/* 스텝 연결선 (데스크톱 가로) */}
          <svg
            viewBox="0 0 1000 8"
            preserveAspectRatio="none"
            className="absolute left-[16%] right-[16%] top-7 hidden h-2 w-[68%] lg:block"
            aria-hidden
          >
            <path
              d="M0 4 L1000 4"
              fill="none"
              pathLength={1}
              strokeDasharray={1}
              className="hiw-line stroke-indigo-300 dark:stroke-indigo-800"
              strokeWidth={3}
            />
          </svg>
          <ol className="grid gap-10 lg:grid-cols-3">
            {howItWorks.steps.map((step, i) => (
              <li key={step.title} className="hiw-step relative text-center">
                <div className="relative z-10 mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-full bg-indigo-600 text-xl font-bold text-white shadow-lg shadow-indigo-600/25">
                  {i + 1}
                </div>
                <h3 className="text-lg font-bold text-slate-900 dark:text-white">{step.title}</h3>
                <p className="mx-auto mt-2 max-w-xs text-sm leading-relaxed text-slate-600 dark:text-slate-400">
                  {step.description}
                </p>
              </li>
            ))}
          </ol>
        </div>
      </div>
    </section>
  );
}
