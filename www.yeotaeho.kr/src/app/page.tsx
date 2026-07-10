// 루트 "/" 페이지 — 랜딩/대시보드 분기는 HomeGate(클라이언트)가 담당, 여기서는 메타데이터만 SSR
import type { Metadata } from "next";
import { HomeGate } from "@/components/features/landing/HomeGate";

export const metadata: Metadata = {
  title: "청년 인사이트 | Global Pulse — AI 진로 내비게이션",
  description:
    "투자 흐름·특허·검색량 등 선행 지표를 분석해 객관적 인사이트와 성장 로드맵을 제공하는 AI 진로 내비게이션 플랫폼.",
  // TODO: OG 이미지 추가 시 openGraph.images 등록 (public/og.png, 1200x630)
};

export default function HomePage() {
  return <HomeGate />;
}
