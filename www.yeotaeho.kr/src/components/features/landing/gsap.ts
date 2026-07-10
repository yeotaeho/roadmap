// 랜딩 전용 GSAP 단일 등록 모듈 — 랜딩 컴포넌트는 gsap을 반드시 이 모듈에서만 import한다
"use client";

import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { useGSAP } from "@gsap/react";

gsap.registerPlugin(ScrollTrigger, useGSAP);

// 반응형·접근성 브레이크포인트 — 섹션별 gsap.matchMedia 조건 공유
export const MM_CONDITIONS = {
  isDesktop: "(min-width: 1024px)",
  isMobile: "(max-width: 1023px)",
  motionOK: "(prefers-reduced-motion: no-preference)",
} as const;

export { gsap, ScrollTrigger, useGSAP };
