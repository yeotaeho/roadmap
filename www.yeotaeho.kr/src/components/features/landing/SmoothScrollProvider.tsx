// 랜딩 전용 Lenis 부드러운 스크롤 프로바이더 — 대시보드 등 앱 셸에는 절대 마운트하지 않는다
"use client";

import { useEffect } from "react";
import Lenis from "lenis";
import { gsap, ScrollTrigger } from "./gsap";

export function SmoothScrollProvider({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    // reduced-motion 환경에서는 네이티브 스크롤 유지
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    const lenis = new Lenis();
    lenis.on("scroll", ScrollTrigger.update);

    const raf = (time: number) => lenis.raf(time * 1000);
    gsap.ticker.add(raf);
    gsap.ticker.lagSmoothing(0);

    return () => {
      gsap.ticker.remove(raf);
      lenis.destroy();
      gsap.ticker.lagSmoothing(500, 33); // gsap 기본값 복원
    };
  }, []);

  return <>{children}</>;
}
