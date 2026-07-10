// 비로그인 방문자용 랜딩 페이지 전체 조립 — Lenis 스무스 스크롤 + GSAP 섹션 연출
"use client";

import { useEffect } from "react";
import "./landing.css";
import { ScrollTrigger } from "./gsap";
import { SmoothScrollProvider } from "./SmoothScrollProvider";
import { LandingHeader } from "./LandingHeader";
import { LandingFooter } from "./LandingFooter";
import { HeroSection } from "./sections/HeroSection";
import { ProblemSection } from "./sections/ProblemSection";
import { StatsSection } from "./sections/StatsSection";
import { FeaturesShowcase } from "./sections/FeaturesShowcase";
import { HowItWorksSection } from "./sections/HowItWorksSection";
import { CtaSection } from "./sections/CtaSection";

export function LandingView() {
  useEffect(() => {
    // 웹폰트 로드 후 핀 구간 재측정 — 레이아웃 시프트로 인한 트리거 오차 방지
    let cancelled = false;
    document.fonts?.ready.then(() => {
      if (!cancelled) ScrollTrigger.refresh();
    });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <SmoothScrollProvider>
      <div className="landing-root bg-white font-sans dark:bg-slate-950">
        <LandingHeader />
        <main>
          <HeroSection />
          <ProblemSection />
          <StatsSection />
          <FeaturesShowcase />
          <HowItWorksSection />
          <CtaSection />
        </main>
        <LandingFooter />
      </div>
    </SmoothScrollProvider>
  );
}
