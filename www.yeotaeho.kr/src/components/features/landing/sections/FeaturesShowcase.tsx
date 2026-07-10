// 랜딩 기능 쇼케이스 — 데스크톱: 핀 고정 + 가로 스크럽 트랙, 모바일: 세로 스택 개별 리빌
"use client";

import { useRef } from "react";
import { gsap, MM_CONDITIONS, useGSAP } from "../gsap";
import { LANDING_COPY, type LandingFeature } from "../landing.copy";
import { FeatureVisual } from "../visuals/FeatureVisuals";

const { features } = LANDING_COPY;

function FeatureCard({ feature }: { feature: LandingFeature }) {
  return (
    <article className="feature-card flex w-[85vw] max-w-md shrink-0 flex-col gap-5 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm dark:border-slate-700 dark:bg-slate-900 sm:p-8 lg:w-[420px]">
      <div className="aspect-[8/5] w-full">
        <FeatureVisual id={feature.id} />
      </div>
      <div>
        <div className="mb-2 flex items-center gap-2">
          <span className="text-lg font-extrabold text-slate-900 dark:text-white">{feature.name}</span>
          <span className="rounded-full bg-indigo-50 px-2.5 py-0.5 text-xs font-semibold text-indigo-600 dark:bg-indigo-950/50 dark:text-indigo-300">
            {feature.tag}
          </span>
        </div>
        <h3 className="text-xl font-bold leading-snug text-slate-900 dark:text-white">
          {feature.headline}
        </h3>
        <p className="mt-2 text-sm leading-relaxed text-slate-600 dark:text-slate-400">
          {feature.description}
        </p>
      </div>
    </article>
  );
}

export function FeaturesShowcase() {
  const ref = useRef<HTMLElement>(null);

  useGSAP(
    () => {
      const mm = gsap.matchMedia();

      // 데스크톱: 섹션 핀 고정 + 트랙 가로 스크럽
      mm.add(`${MM_CONDITIONS.isDesktop} and ${MM_CONDITIONS.motionOK}`, () => {
        const track = ref.current?.querySelector<HTMLElement>(".features-track");
        if (!track) return;
        const distance = () => track.scrollWidth - window.innerWidth;
        gsap.to(track, {
          x: () => -distance(),
          ease: "none",
          scrollTrigger: {
            trigger: ref.current,
            start: "top top",
            end: () => `+=${distance()}`,
            pin: true,
            scrub: 1,
            invalidateOnRefresh: true,
          },
        });
      });

      // 모바일(모션 허용): 카드 개별 리빌
      mm.add(`${MM_CONDITIONS.isMobile} and ${MM_CONDITIONS.motionOK}`, () => {
        gsap.utils.toArray<HTMLElement>(".feature-card").forEach((card) => {
          gsap.from(card, {
            y: 36,
            opacity: 0,
            duration: 0.7,
            ease: "power3.out",
            scrollTrigger: { trigger: card, start: "top 85%", once: true },
          });
        });
      });
      return () => mm.revert(); // unmount 시 media query 리스너까지 확실히 해제
    },
    { scope: ref }
  );

  return (
    <section ref={ref} className="overflow-hidden bg-slate-50 dark:bg-slate-900">
      <div className="flex min-h-screen flex-col justify-center py-20 lg:py-0">
        <div className="mx-auto mb-12 max-w-6xl px-4 text-center sm:px-6 lg:px-8">
          <h2 className="text-3xl font-extrabold tracking-tight text-slate-900 dark:text-white sm:text-4xl">
            {features.title}
          </h2>
          <p className="mt-3 text-base text-slate-600 dark:text-slate-400">{features.subtitle}</p>
        </div>
        <div className="features-track flex flex-col items-center gap-6 px-4 sm:px-6 lg:flex-row lg:items-stretch lg:gap-8 lg:px-[8vw]">
          {features.items.map((feature) => (
            <FeatureCard key={feature.id} feature={feature} />
          ))}
        </div>
      </div>
    </section>
  );
}
