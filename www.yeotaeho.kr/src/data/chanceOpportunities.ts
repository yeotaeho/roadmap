export type ChanceOpportunityId =
  | "youth-ai-hackathon-2026"
  | "ai-bootcamp-7"
  | "esg-data-internship";

export type ChanceOpportunityCard = {
  id: ChanceOpportunityId;
  title: string;
  type: string;
  dday: string;
  match: number;
};

export type ChanceOpportunityDetail = ChanceOpportunityCard & {
  summary: string;
  eligibility: string[];
  prepare: string[];
  links: { label: string; href: string }[];
};

export const CHANCE_OPPORTUNITIES: readonly ChanceOpportunityCard[] = [
  {
    id: "youth-ai-hackathon-2026",
    title: "2026 청년 AI 혁신 공모전",
    type: "공모전",
    dday: "D-3",
    match: 85,
  },
  {
    id: "ai-bootcamp-7",
    title: "AI 인재 양성 부트캠프 7기",
    type: "교육",
    dday: "D-6",
    match: 78,
  },
  {
    id: "esg-data-internship",
    title: "ESG 데이터 분석 인턴십",
    type: "채용",
    dday: "D-10",
    match: 82,
  },
] as const;

const CHANCE_DETAIL_BY_ID: Record<ChanceOpportunityId, ChanceOpportunityDetail> = {
  "youth-ai-hackathon-2026": {
    ...CHANCE_OPPORTUNITIES[0],
    summary:
      "팀 빌딩·문제정의·프로토타입까지 빠르게 돌려야 하는 형식입니다. 백엔드/데이터 기반이 있으면 ‘현장 문제 → 데모’로 연결하기 좋습니다.",
    eligibility: ["청년(연령 기준은 공고문 확인)", "팀 또는 개인 참가 규정 확인", "제출물 형식(PDF/영상/깃허브) 준수"],
    prepare: [
      "아이디어 1p(문제/고객/가설/지표) 정리",
      "데모 범위를 48시간 내 완성 가능한 크기로 축소",
      "발표 스토리라인(왜 지금인가) 작성",
    ],
    links: [
      { label: "공식 공고(예시 링크)", href: "https://example.com/notice" },
      { label: "팀 모집/규정(예시)", href: "https://example.com/rules" },
    ],
  },
  "ai-bootcamp-7": {
    ...CHANCE_OPPORTUNITIES[1],
    summary:
      "짧은 기간에 실무 프로젝트 중심으로 커리큘럼이 압축됩니다. 선발에서 기초 역량(파이썬/깃/HTTP)과 학습 태도를 강하게 봅니다.",
    eligibility: ["지원 자격(학력/경력) 공고 확인", "사전 과제 여부 확인", "시간 풀타임 가능 여부"],
    prepare: [
      "Python 기본기 + 간단한 API 서버 과제 1개",
      "포트폴리오 README에 문제/결과/회고 구조화",
      "면접에서 말할 ‘학습 계획 30일’ 준비",
    ],
    links: [{ label: "커리큘럼/일정(예시)", href: "https://example.com" }],
  },
  "esg-data-internship": {
    ...CHANCE_OPPORTUNITIES[2],
    summary:
      "ESG 데이터는 정의가 흔들리기 쉬워, ‘지표를 어떻게 만들고 검증할지’가 핵심입니다. SQL/대시보드/감사 로그에 강점이 있으면 매칭이 좋아집니다.",
    eligibility: ["데이터 분석 경험(학교 과제/프로젝트 포함)", "SQL 필수 여부 확인", "근무 지역/일정 확인"],
    prepare: [
      "KPI 정의서 템플릿(문제-지표-데이터-검증) 1건 작성",
      "샘플 데이터로 대시보드 1장 만들기",
      "개인정보/저작권 이슈 체크리스트 정리",
    ],
    links: [{ label: "채용 공고(예시)", href: "https://example.com" }],
  },
};

export function getChanceOpportunityDetail(id: string) {
  if (
    id !== "youth-ai-hackathon-2026" &&
    id !== "ai-bootcamp-7" &&
    id !== "esg-data-internship"
  ) {
    return null;
  }
  return CHANCE_DETAIL_BY_ID[id];
}

export function getAllChanceOpportunityIds(): ChanceOpportunityId[] {
  return CHANCE_OPPORTUNITIES.map((o) => o.id);
}
