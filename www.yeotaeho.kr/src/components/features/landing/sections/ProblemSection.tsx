// 랜딩 문제 공감 섹션 — 핀 고정 후 워드 단위 opacity 스크럽 리빌
"use client";

import { useRef } from "react";
import { gsap, MM_CONDITIONS, useGSAP } from "../gsap";
import { LANDING_COPY } from "../landing.copy";

export function ProblemSection() {
  const ref = useRef<HTMLElement>(null);

  useGSAP(
    () => {
      const mm = gsap.matchMedia();
      mm.add(MM_CONDITIONS.motionOK, () => {
        gsap.fromTo(
          ".problem-word",
          { opacity: 0.15 },
          {
            opacity: 1,
            stagger: 0.4,
            ease: "none",
            scrollTrigger: {
              trigger: ref.current,
              start: "top top",
              end: "+=140%",
              pin: true,
              scrub: 0.5,
            },
          }
        );
      });
      return () => mm.revert(); // unmount 시 media query 리스너까지 확실히 해제
    },
    { scope: ref }
  );

  return (
    <section
      ref={ref}
      className="flex min-h-screen items-center bg-slate-50 dark:bg-slate-900"
    >
      <div className="mx-auto max-w-4xl px-4 sm:px-6">
        <div className="space-y-6">
          {LANDING_COPY.problem.lines.map((line) => (
            <p
              key={line}
              className="text-2xl font-bold leading-snug text-slate-900 dark:text-white sm:text-4xl lg:text-5xl"
            >
              {line.split(" ").map((word, i) => (
                <span key={`${word}-${i}`} className="problem-word inline-block whitespace-pre">
                  {word}{" "}
                </span>
              ))}
            </p>
          ))}
        </div>
      </div>
    </section>
  );
}
