/** AI 코치 — 데모 맥락·액티브 로드맵 요약 (추후 API로 치환) */

export type CoachContextSource = "chance" | "roadmap" | "pulse";

export type CoachAttachedContext = {
  id: string;
  source: CoachContextSource;
  /** 입력창 위 맥락 지시자 한 줄 */
  label: string;
};

export type CoachWalletItem = {
  id: string;
  title: string;
  body: string;
  createdAt: number;
};

export const DEMO_ATTACHED_CONTEXTS: Record<string, CoachAttachedContext> = {
  chance: {
    id: "ctx-chance-1",
    source: "chance",
    label:
      "그린테크 스타트업 백엔드 엔지니어 채용 (필수: 대용량 데이터 파이프라인, 우대: ESG 공시 이해도)",
  },
  roadmap: {
    id: "ctx-roadmap-1",
    source: "roadmap",
    label: "진행 중인 퀘스트: 탄소 배출 룰 기반 계산 엔진 · 스키마·가중치 모듈 분리",
  },
};

/** 우측 Active Context 카드 (로드맵 연동 요약) */
export const COACH_ACTIVE_FOCUS = {
  title: "현재 집중 목표",
  subtitle: "IFRS S1/S2 데이터 맵핑",
  body: "탄소 배출 룰 기반 계산 엔진 — 스키마 단계에서 엔티티 경계와 가중치 정책을 분리해 두면 이후 파이프라인·공시 매핑까지 확장하기 쉽습니다.",
  tags: ["FastAPI", "PostgreSQL", "ESG 공시", "파이프라인"],
};
