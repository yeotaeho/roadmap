export type PulseSectorSlug =
  | "ai-data"
  | "sustainability-esg"
  | "bio-health-tech"
  | "future-finance"
  | "next-gen-media"
  | "smart-manufacturing";

export type PulseSectorCard = {
  slug: PulseSectorSlug;
  title: string;
  score: number;
  status: string;
  color: string;
  badgeInfo: string;
};

export const PULSE_SECTORS = [
  {
    slug: "ai-data",
    title: "지능형 기술 (AI & Data)",
    score: 92,
    status: "태풍급",
    color: "bg-indigo-500",
    badgeInfo: "bg-indigo-100 text-indigo-600",
  },
  {
    slug: "sustainability-esg",
    title: "지속 가능성 (Sustainability & ESG)",
    score: 84,
    status: "급상승",
    color: "bg-emerald-400",
    badgeInfo: "bg-emerald-100 text-emerald-600",
  },
  {
    slug: "bio-health-tech",
    title: "바이오·헬스테크 (Bio & Health-Tech)",
    score: 73,
    status: "상승",
    color: "bg-teal-400",
    badgeInfo: "bg-teal-100 text-teal-600",
  },
  {
    slug: "future-finance",
    title: "미래 금융 (Future Finance)",
    score: 69,
    status: "관찰",
    color: "bg-purple-400",
    badgeInfo: "bg-purple-100 text-purple-600",
  },
  {
    slug: "next-gen-media",
    title: "콘텐츠/IP (Next-Gen Media)",
    score: 64,
    status: "재정렬",
    color: "bg-amber-400",
    badgeInfo: "bg-amber-100 text-amber-600",
  },
  {
    slug: "smart-manufacturing",
    title: "지능형 제조 (Smart Manufacturing)",
    score: 78,
    status: "회복",
    color: "bg-blue-400",
    badgeInfo: "bg-blue-100 text-blue-600",
  },
] as const satisfies readonly PulseSectorCard[];

type PulseSectorDetail = {
  headline: string;
  whyItMatters: string[];
  signals: { label: string; value: string }[];
  risks: string[];
  actions: { label: string; href: string }[];
};

const PULSE_SECTOR_DETAIL_BY_SLUG: Record<PulseSectorSlug, PulseSectorDetail> = {
  "ai-data": {
    headline: "LLM·데이터 파이프라인·자동화가 동시에 가속화되는 구간입니다.",
    whyItMatters: [
      "생산성 도구가 ‘선택’이 아니라 ‘운영’으로 들어가며 채용/프로젝트가 빠르게 늘어납니다.",
      "보안·거버넌스 이슈가 같이 따라와 엔지니어링 난이도가 올라갑니다.",
    ],
    signals: [
      { label: "주간 속도 지수(예시)", value: "86 / 100" },
      { label: "핵심 키워드(예시)", value: "RAG, Agent, MLOps" },
      { label: "채용/공고 신호(예시)", value: "백엔드·보안 직군 증가" },
    ],
    risks: [
      "기술 스택이 빠르게 갈아엎여 학습 부채가 누적될 수 있습니다.",
      "‘AI’라는 이름의 과대포장 공고가 섞일 수 있어 근거 확인이 필요합니다.",
    ],
    actions: [
      { label: "AI 코치에게 물어보기", href: "/coach" },
      { label: "대시보드로 돌아가기", href: "/" },
    ],
  },
  "sustainability-esg": {
    headline: "정책·자본·규제가 맞물리며 데이터 기반 의사결정 수요가 커집니다.",
    whyItMatters: [
      "배출·공급망 데이터의 투명성 요구가 강해지며 분석/감사 자동화가 핵심이 됩니다.",
      "대기업 규제 대응이 중소·파트너사로 전파되며 실무 프로젝트가 늘어납니다.",
    ],
    signals: [
      { label: "정책/규제 키워드(예시)", value: "CBAM, 배출권, 공시" },
      { label: "산업 신호(예시)", value: "데이터 품질·감사 로그" },
      { label: "기회 직무(예시)", value: "ESG 데이터·리스크 분석" },
    ],
    risks: [
      "데이터 소스가 분산되어 표준화/정합성 이슈가 크게 나타날 수 있습니다.",
      "규제 해석이 국가별로 달라 포트폴리오 설계가 어려울 수 있습니다.",
    ],
    actions: [
      { label: "AI 코치에게 물어보기", href: "/coach" },
      { label: "대시보드로 돌아가기", href: "/" },
    ],
  },
  "bio-health-tech": {
    headline: "디지털 헬스·바이오데이터·개인정보 보호가 동시에 중요해집니다.",
    whyItMatters: [
      "임상/운영 데이터의 품질과 보안이 제품 신뢰의 핵심 경쟁력이 됩니다.",
      "규제(의료기기/개인정보) 대응 역량이 엔지니어링에 직접 연결됩니다.",
    ],
    signals: [
      { label: "핵심 키워드(예시)", value: "FHIR, EMR, Privacy" },
      { label: "수요 신호(예시)", value: "분석·보안·컴플라이언스" },
      { label: "협업 신호(예시)", value: "병원·제약·스타트업 파트너십" },
    ],
    risks: [
      "민감 데이터 취급으로 보안 사고 리스크가 큽니다.",
      "검증/인증 주기가 길어 POC→상용까지 시간이 걸릴 수 있습니다.",
    ],
    actions: [
      { label: "AI 코치에게 물어보기", href: "/coach" },
      { label: "대시보드로 돌아가기", href: "/" },
    ],
  },
  "future-finance": {
    headline: "금융의 디지털화는 ‘속도’보다 ‘신뢰(보안/컴플라이언스)’가 승패를 가릅니다.",
    whyItMatters: [
      "결제/정보보호/사기탐지가 기술 중심으로 재편되며 엔지니어 비중이 커집니다.",
      "규제 샌드박스·오픈뱅킹 등 환경 변화가 제품 로드맵에 직접 영향을 줍니다.",
    ],
    signals: [
      { label: "핵심 키워드(예시)", value: "AML/KYC, 결제보안, 인증" },
      { label: "채용 신호(예시)", value: "백엔드·보안·데이터" },
      { label: "시장 신호(예시)", value: "B2B 핀테크 인프라" },
    ],
    risks: [
      "규제 변화에 따른 리팩터링 비용이 큽니다.",
      "외부 공급자(카드/은행) 연동 이슈로 일정이 지연될 수 있습니다.",
    ],
    actions: [
      { label: "AI 코치에게 물어보기", href: "/coach" },
      { label: "대시보드로 돌아가기", href: "/" },
    ],
  },
  "next-gen-media": {
    headline: "콘텐츠는 ‘제작’에서 ‘유통·개인화·IP 비즈니스’로 이동 중입니다.",
    whyItMatters: [
      "플랫폼 알고리즘/권리/수익화가 결합되며 데이터 역량이 경쟁력이 됩니다.",
      "툴 체인(AI 생성·에디팅·분석)이 빠르게 진화합니다.",
    ],
    signals: [
      { label: "핵심 키워드(예시)", value: "IP, 숏폼, 라이선스" },
      { label: "수요 신호(예시)", value: "기획·그로스·분석" },
      { label: "기술 신호(예시)", value: "추천/썸네일/자동편집" },
    ],
    risks: [
      "저작권/표절 이슈가 비즈니스 리스크로 직결됩니다.",
      "플랫폼 정책 변화에 따라 트래픽이 급변할 수 있습니다.",
    ],
    actions: [
      { label: "AI 코치에게 물어보기", href: "/coach" },
      { label: "대시보드로 돌아가기", href: "/" },
    ],
  },
  "smart-manufacturing": {
    headline: "공급망 리스크와 자동화가 겹치며 ‘현장 데이터’의 가치가 커집니다.",
    whyItMatters: [
      "설비/물류/품질 데이터를 실시간으로 다루는 SW 역량이 핵심입니다.",
      "로보틱스·비전·엣지가 결합되며 융합 인재 수요가 늘어납니다.",
    ],
    signals: [
      { label: "핵심 키워드(예시)", value: "MES, SCADA, Digital Twin" },
      { label: "수요 신호(예시)", value: "엣지·OT 보안" },
      { label: "시장 신호(예시)", value: "리쇼어링/국산화" },
    ],
    risks: [
      "OT/IT 경계 문제로 보안 사고 영향이 큽니다.",
      "현장 도입은 PoC와 운영의 간극이 크기 쉽습니다.",
    ],
    actions: [
      { label: "AI 코치에게 물어보기", href: "/coach" },
      { label: "대시보드로 돌아가기", href: "/" },
    ],
  },
};

export function getPulseSectorBundle(slug: string) {
  const sector = PULSE_SECTORS.find((s) => s.slug === slug);
  if (!sector) return null;
  const detail = PULSE_SECTOR_DETAIL_BY_SLUG[sector.slug];
  return { sector, detail };
}

export function getAllPulseSectorSlugs(): PulseSectorSlug[] {
  return PULSE_SECTORS.map((s) => s.slug);
}
