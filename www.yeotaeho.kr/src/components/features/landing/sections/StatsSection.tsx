// 랜딩 지표 섹션 — 뷰포트 진입 시 1회 숫자 카운트업
"use client";

import { useRef } from "react";
import { gsap, MM_CONDITIONS, useGSAP } from "../gsap";
import { LANDING_COPY } from "../landing.copy";

const { stats } = LANDING_COPY;

export function StatsSection() {
  const ref = useRef<HTMLElement>(null);

  useGSAP(
    () => {
      const mm = gsap.matchMedia();
      mm.add(MM_CONDITIONS.motionOK, () => {
        // 마크업 기본값은 최종 수치(SSR·reduce 대비) — 진입 시 0부터 카운트업
        gsap.utils.toArray<HTMLElement>(".stat-value").forEach((el) => {
          const target = Number(el.dataset.value ?? "0");
          gsap.fromTo(
            el,
            { textContent: 0 },
            {
              textContent: target,
              duration: 1.6,
              ease: "power2.out",
              snap: { textContent: 1 },
              scrollTrigger: { trigger: el, start: "top 85%", once: true },
            }
          );
        });
        gsap.from(".stat-item", {
          y: 28,
          opacity: 0,
          duration: 0.7,
          stagger: 0.1,
          ease: "power3.out",
          scrollTrigger: { trigger: ref.current, start: "top 75%", once: true },
        });
      });
    },
    { scope: ref }
  );

  return (
    <section ref={ref} className="bg-white py-24 dark:bg-slate-950 sm:py-32">
      <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
        <h2 className="mb-14 text-center text-2xl font-bold text-slate-900 dark:text-white sm:text-3xl">
          {stats.title}
        </h2>
        <dl className="grid grid-cols-2 gap-8 lg:grid-cols-4">
          {stats.items.map((item) => (
            <div key={item.label} className="stat-item text-center">
              <dd className="text-4xl font-extrabold tracking-tight text-indigo-600 dark:text-indigo-400 sm:text-5xl">
                <span className="stat-value" data-value={item.value}>
                  {item.value}
                </span>
                <span className="text-2xl sm:text-3xl">{item.suffix}</span>
              </dd>
              <dt className="mt-3 text-sm font-medium text-slate-500 dark:text-slate-400">
                {item.label}
              </dt>
            </div>
          ))}
        </dl>
      </div>
    </section>
  );
}
