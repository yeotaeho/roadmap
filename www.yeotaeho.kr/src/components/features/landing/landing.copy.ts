// 랜딩 페이지 카피 상수 — 텍스트 교체는 이 파일만 수정하면 된다 (마크업에 문자열 하드코딩 금지)

export const LANDING_COPY = {
  brand: {
    name: "청년 인사이트",
    sub: "Global Pulse",
  },

  header: {
    login: { label: "로그인", href: "/login" },
    start: { label: "시작하기", href: "/signup" },
  },

  hero: {
    eyebrow: "AI 진로 내비게이션",
    titleLines: ["막연함을 데이터로,", "가능성을 로드맵으로."],
    subtitle:
      "투자 흐름·특허·검색량 — 세상이 먼저 움직이는 신호를 읽고, 당신의 다음 행동을 설계하는 AI 진로 내비게이션.",
    primaryCta: { label: "무료로 시작하기", href: "/signup" },
    secondaryCta: { label: "로그인", href: "/login" },
    scrollHint: "스크롤해서 살펴보기",
  },

  problem: {
    lines: [
      "무엇을 준비해야 할지 막막한가요?",
      "정보는 넘치는데, 나의 방향은 보이지 않나요?",
      "감이 아니라 데이터로 결정할 시간입니다.",
    ],
  },

  stats: {
    title: "세상의 신호를 매일 읽습니다",
    items: [
      { value: 12, suffix: "개", label: "라이브 산업 섹터" },
      { value: 3, suffix: "종", label: "선행 행동 지표" },
      { value: 365, suffix: "일", label: "매일 갱신되는 싱크로율" },
      { value: 4, suffix: "채널", label: "채용·부트캠프·공모전·지원사업" },
    ],
  },

  features: {
    title: "여섯 개의 나침반",
    subtitle: "흐름을 읽는 것부터 실행까지, 하나의 여정으로 이어집니다.",
    items: [
      {
        id: "pulse",
        name: "Pulse",
        tag: "트렌드 레이더",
        headline: "12개 섹터의 흐름을 매일 점수로",
        description:
          "투자·특허·검색량 같은 선행 지표를 융합해 산업 섹터별 트렌드 점수와 경제 브리핑을 매일 갱신합니다.",
      },
      {
        id: "gap",
        name: "Gap",
        tag: "블루오션",
        headline: "아직 아무도 풀지 않은 기회",
        description:
          "시장의 미해결 문제를 근거 데이터와 함께 시각화해, 남들이 보지 못한 빈틈을 먼저 발견하게 합니다.",
      },
      {
        id: "sync",
        name: "Sync",
        tag: "싱크로율",
        headline: "나와 트렌드의 적합도를 매일",
        description:
          "내 프로필과 세상의 흐름이 얼마나 맞물리는지 일별 점수로 추적합니다. 방향이 맞는지 매일 확인하세요.",
      },
      {
        id: "chance",
        name: "Chance",
        tag: "다이렉트 찬스",
        headline: "지금 잡을 수 있는 기회 매칭",
        description:
          "채용·부트캠프·공모전·지원사업 네 채널에서 나에게 맞는 기회를 골라 연결합니다.",
      },
      {
        id: "roadmap",
        name: "Roadmap",
        tag: "전략 로드맵",
        headline: "AI가 설계하는 퀘스트 트리",
        description:
          "목표까지의 여정을 퀘스트 트리로 쪼개고, 완료한 성장 기록은 아카이브로 쌓입니다.",
      },
      {
        id: "coach",
        name: "Coach",
        tag: "AI 상담실",
        headline: "자기이해 기반 실시간 멘토링",
        description:
          "대화로 성향(RIASEC·Big Five)을 읽어내는 AI 상담과 실시간 스트리밍 멘토링이 다음 걸음을 함께 정합니다.",
      },
    ],
  },

  howItWorks: {
    title: "3단계로 시작하세요",
    steps: [
      {
        title: "프로필 온보딩",
        description: "관심 분야와 경험을 알려주세요. 3분이면 충분합니다.",
      },
      {
        title: "AI 지표 분석",
        description: "선행 지표와 내 프로필을 매일 대조해 방향을 잡아줍니다.",
      },
      {
        title: "로드맵 실행",
        description: "AI가 설계한 퀘스트를 하나씩 완료하며 성장 기록을 쌓으세요.",
      },
    ],
  },

  cta: {
    title: "지금, 나의 방향을 확인하세요",
    subtitle: "데이터가 가리키는 다음 걸음을 무료로 만나보세요.",
    button: { label: "무료로 시작하기", href: "/signup" },
  },

  footer: {
    copyright: "© 2026 청년 인사이트 · Global Pulse",
    links: [
      { label: "로그인", href: "/login" },
      { label: "회원가입", href: "/signup" },
    ],
  },
} as const;

export type LandingFeature = (typeof LANDING_COPY.features.items)[number];
export type LandingFeatureId = LandingFeature["id"];
