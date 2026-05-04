export type GapIssueId = "esg-market-transparency" | "enterprise-rag-quality";

export type GapIssueCard = {
  id: GapIssueId;
  problem: string;
  chance: string;
};

export type GapIssueDetail = GapIssueCard & {
  summary: string;
  stakeholders: string[];
  nextSteps: string[];
};

export const GAP_ISSUES: readonly GapIssueCard[] = [
  {
    id: "esg-market-transparency",
    problem: "탄소 배출권 거래 시장의 데이터 투명성 부족",
    chance: "ESG 데이터 분석가·감사 자동화 솔루션 수요 급증",
  },
  {
    id: "enterprise-rag-quality",
    problem: "기업 LLM 도입 후 사내 지식검색(RAG) 품질 편차 확대",
    chance: "RAG 엔지니어·검색 최적화 아키텍트 수요 증가",
  },
] as const;

const GAP_ISSUE_DETAIL_BY_ID: Record<GapIssueId, GapIssueDetail> = {
  "esg-market-transparency": {
    ...GAP_ISSUES[0],
    summary:
      "배출권·공급망 데이터의 신뢰성이 확보되지 않으면 기업의 감사·공시·거래 비용이 폭증합니다. 데이터 파이프라인과 검증(계측/로그)이 핵심 경쟁력이 됩니다.",
    stakeholders: ["ESG/컴플라이언스", "데이터 엔지니어링", "감사(내부회계)", "공급망 운영"],
    nextSteps: [
      "데이터 소스(ERP/SCM/IoT) 목록화와 품질 지표 정의",
      "감사 추적 가능한 파이프라인(버전/출처) 설계",
      "PoC 범위를 ‘보고’가 아니라 ‘자동 검증’으로 좁히기",
    ],
  },
  "enterprise-rag-quality": {
    ...GAP_ISSUES[1],
    summary:
      "RAG는 도입이 쉬워 보이지만, 청킹·임베딩·재랭킹·권한/보안·평가루프가 어긋나면 품질이 급락합니다. ‘검색 품질 엔지니어링’이 별도 직무로 분리되는 흐름이 강해집니다.",
    stakeholders: ["플랫폼 엔지니어", "보안", "지식관리(KM)", "법무/컴플라이언스"],
    nextSteps: [
      "문서 권한 모델(부서/기밀)과 검색 결과 노출 정책 정리",
      "오프라인 평가셋(질문-정답 근거) 구축",
      "재현 가능한 배포/롤백(모델/인덱스) 파이프라인 만들기",
    ],
  },
};

export function getGapIssueDetail(id: string) {
  if (id !== "esg-market-transparency" && id !== "enterprise-rag-quality") return null;
  return GAP_ISSUE_DETAIL_BY_ID[id];
}

export function getAllGapIssueIds(): GapIssueId[] {
  return GAP_ISSUES.map((c) => c.id);
}
