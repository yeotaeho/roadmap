// 온보딩 1회 유도 — 로그인 후 미완료 플래그 없으면 /onboarding 으로

const FLAG = "roadmap_onboarding_done";

export function onboardingTarget(): string {
  if (typeof window === "undefined") return "/";
  return localStorage.getItem(FLAG) ? "/" : "/onboarding";
}

export function markOnboardingDone(): void {
  if (typeof window !== "undefined") localStorage.setItem(FLAG, "1");
}
