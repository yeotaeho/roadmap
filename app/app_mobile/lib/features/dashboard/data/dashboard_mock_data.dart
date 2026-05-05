import 'package:flutter/material.dart';

import '../../../core/theme/app_colors.dart';

/// 웹 `pulseSectors.ts` / `gapIssues.ts` / `chanceOpportunities.ts` 와 동일한 데모 데이터.

class PulseSectorCard {
  const PulseSectorCard({
    required this.slug,
    required this.title,
    required this.score,
    required this.status,
    required this.accent,
  });

  final String slug;
  final String title;
  final int score;
  final String status;
  final Color accent;
}

class PulseSectorDetail {
  const PulseSectorDetail({
    required this.headline,
    required this.whyItMatters,
    required this.signals,
    required this.risks,
  });

  final String headline;
  final List<String> whyItMatters;
  final List<({String label, String value})> signals;
  final List<String> risks;
}

class GapIssueCard {
  const GapIssueCard({
    required this.id,
    required this.sectorId,
    required this.problem,
    required this.chance,
  });

  final String id;
  /// [pulseSectors] 항목 `slug`와 일치 (Top 6 분야).
  final String sectorId;
  final String problem;
  final String chance;
}

class GapIssueDetail extends GapIssueCard {
  const GapIssueDetail({
    required super.id,
    required super.sectorId,
    required super.problem,
    required super.chance,
    required this.summary,
    required this.stakeholders,
    required this.nextSteps,
  });

  final String summary;
  final List<String> stakeholders;
  final List<String> nextSteps;
}

class ChanceCard {
  const ChanceCard({
    required this.id,
    required this.title,
    required this.type,
    required this.dday,
    required this.match,
  });

  final String id;
  final String title;
  final String type;
  final String dday;
  final int match;
}

class ChanceDetail extends ChanceCard {
  const ChanceDetail({
    required super.id,
    required super.title,
    required super.type,
    required super.dday,
    required super.match,
    required this.summary,
    required this.eligibility,
    required this.prepare,
  });

  final String summary;
  final List<String> eligibility;
  final List<String> prepare;
}

class GlobalPulseSummary {
  const GlobalPulseSummary({
    required this.speedLabel,
    required this.deltaLabel,
    required this.weekIndex,
    required this.insightLine,
  });

  final String speedLabel;
  final String deltaLabel;
  final String weekIndex;
  final String insightLine;
}

/// 펄스 히어로(속도계) — 웹 글로벌 펄스 헤더 대응.
class PulseHeroMock {
  const PulseHeroMock({
    required this.speedKmh,
    required this.weekIndex,
    required this.weekMax,
    required this.deltaShort,
    required this.insightLine,
    required this.unitLabel,
    required this.speedContextLine,
  });

  final int speedKmh;
  final int weekIndex;
  final int weekMax;
  final String deltaShort;
  final String insightLine;
  final String unitLabel;
  /// 웹 상단 서브카피 (예: AI·보안·클라우드 급상승).
  final String speedContextLine;
}

class CausalStepMock {
  const CausalStepMock({
    required this.badge,
    required this.title,
    required this.detail,
  });

  final String badge;
  final String title;
  final String detail;
}

class BriefingSlideMock {
  const BriefingSlideMock({
    required this.tag,
    required this.headline,
    required this.body,
  });

  final String tag;
  final String headline;
  final String body;
}

/// 3줄 경제 브리핑(웹 우측 리스트 대응).
enum PulseBriefingVisual { fxUp, rateHold, topicPulse }

class PulseBriefingLineMock {
  const PulseBriefingLineMock({
    required this.headline,
    required this.body,
    required this.visual,
  });

  final String headline;
  final String body;
  final PulseBriefingVisual visual;
}

class PulseShareSliceMock {
  const PulseShareSliceMock({
    required this.label,
    required this.fraction,
  });

  final String label;
  final double fraction;
}

class SyncOverviewMock {
  const SyncOverviewMock({
    required this.score,
    required this.deltaWeek,
    required this.topTrends,
    required this.reasonLines,
    required this.keywordEvidence,
  });

  final int score;
  final int deltaWeek;
  final List<String> topTrends;
  final List<String> reasonLines;
  final String keywordEvidence;
}

abstract final class DashboardMockData {
  static const GlobalPulseSummary pulseSummary = GlobalPulseSummary(
    speedLabel: '가속',
    deltaLabel: '전일 대비 +2',
    weekIndex: '주간 지수 86/100',
    insightLine: '정책·자본이 데이터 인프라 쪽으로 기우는 한 주입니다.',
  );

  static const PulseHeroMock pulseHero = PulseHeroMock(
    speedKmh: 180,
    weekIndex: 86,
    weekMax: 100,
    deltaShort: '전일 대비 +2',
    insightLine: '정책·자본이 데이터 인프라 쪽으로 기우는 한 주입니다.',
    unitLabel: 'km/h',
    speedContextLine: 'AI·보안·클라우드 급상승',
  );

  static const List<CausalStepMock> pulseCausalChain = [
    CausalStepMock(
      badge: '거시 이벤트',
      title: '미국 금리 인하 시그널 강화',
      detail: '금리·환율 변동성 축소 기대가 성장주·테크 밸류에이션에 호재로 작동할 수 있습니다.',
    ),
    CausalStepMock(
      badge: '산업 영향',
      title: '빅테크의 AI·클라우드 투자 가속화',
      detail: '인프라·보안·데이터 파이프라인 CapEx가 늘며 관련 직군 공고가 구조적으로 상향됩니다.',
    ),
    CausalStepMock(
      badge: '청년 기회',
      title: 'AI 백엔드/보안 엔지니어 채용 수요 확대',
      detail: '레거시 연동·권한·관측성 요구가 커지며 풀스택 대비 ‘운영 가능한’ 역량이 가산점이 됩니다.',
    ),
  ];

  /// Top 섹터 히트맵 — 행: 섹터, 열: 태동기·급상승·성숙·쇠퇴 (셀 점수 0~100).
  static const List<String> pulseHeatmapStages = ['태동기', '급상승', '성숙', '쇠퇴'];
  static const List<String> pulseHeatmapRowLabels = [
    '지능형 기술',
    '지속·ESG',
    '바이오·헬스',
    '미래 금융',
    '콘텐츠/IP',
    '스마트 제조',
  ];
  static const List<List<int>> pulseHeatmapScores = [
    [44, 92, 74, 31],
    [39, 86, 78, 35],
    [36, 71, 82, 41],
    [46, 64, 69, 44],
    [49, 57, 63, 51],
    [34, 79, 76, 36],
  ];

  static const List<String> pulseTickerItems = [
    'KOSPI 변동성 확대',
    '달러/원 1,412원',
    '클라우드 보안 투자 증가',
    '반도체 재고 조정 둔화',
    '청년 채용 공고 AI 키워드 ↑',
    '금리 선물 변동성 축소',
    '에너지 전환 테마 재개장',
  ];

  static const List<String> pulseRisingKeywords = [
    'LLM',
    '배터리',
    'ESG',
    'FastAPI',
    '콘텐츠기획',
    'LangGraph',
    'RAG',
    'MLOps',
  ];

  static const List<PulseBriefingLineMock> pulseBriefingThreeLines = [
    PulseBriefingLineMock(
      visual: PulseBriefingVisual.fxUp,
      headline: '환율 상승',
      body: '해외 취업 준비 비용과 IT 수입 단가에 영향',
    ),
    PulseBriefingLineMock(
      visual: PulseBriefingVisual.rateHold,
      headline: '금리 동결',
      body: '청년 대출·전세 자금 부담 완화 기대',
    ),
    PulseBriefingLineMock(
      visual: PulseBriefingVisual.topicPulse,
      headline: '이번 주 키워드',
      body: 'AI 규제, 에너지 전환',
    ),
  ];

  /// 세대교체 — 기존 수요 vs 신규 수요 (교차 시점 x 인덱스는 플롯 좌표).
  static const List<double> pulseCrossoverLegacy = [82, 77, 71, 64, 57, 51, 47];
  static const List<double> pulseCrossoverNew = [36, 42, 51, 62, 72, 80, 87];
  static const double pulseCrossoverAtX = 3.35;

  static const List<BriefingSlideMock> pulseBriefingSlides = [
    BriefingSlideMock(
      tag: '금융',
      headline: '실물·금융 조건 완화 기대',
      body: '유동성 전환 국면에서 성장주·테마 변동성이 동반 확대될 수 있습니다.',
    ),
    BriefingSlideMock(
      tag: '정책',
      headline: '공급망·배출 데이터 규제 강화',
      body: 'ESG 데이터 파이프라인·감사 로그 인력 수요가 중소까지 전파됩니다.',
    ),
    BriefingSlideMock(
      tag: '노동',
      headline: 'AI 보조 코딩 확산',
      body: '프로덕트 속도는 빨라지지만 코드 리뷰·보안 거버넌스 비용도 함께 커집니다.',
    ),
  ];

  /// 연간 트렌드 지수(데모 Y값 0~100).
  static const List<double> pulseAnnualTrendSeries = [62, 66, 69, 73, 77, 81, 86];

  static const List<PulseShareSliceMock> pulseSectorShares = [
    PulseShareSliceMock(label: 'AI·데이터', fraction: 0.28),
    PulseShareSliceMock(label: 'ESG·지속', fraction: 0.22),
    PulseShareSliceMock(label: '미래 금융', fraction: 0.18),
    PulseShareSliceMock(label: '바이오·헬스', fraction: 0.14),
    PulseShareSliceMock(label: '기타', fraction: 0.18),
  ];

  static const List<PulseSectorCard> pulseSectors = [
    PulseSectorCard(
      slug: 'ai-data',
      title: '지능형 기술 (AI & Data)',
      score: 92,
      status: '태풍급',
      accent: AppColors.sectorMetricAccent,
    ),
    PulseSectorCard(
      slug: 'sustainability-esg',
      title: '지속 가능성 (Sustainability & ESG)',
      score: 84,
      status: '급상승',
      accent: AppColors.sectorMetricAccent,
    ),
    PulseSectorCard(
      slug: 'bio-health-tech',
      title: '바이오·헬스테크',
      score: 73,
      status: '상승',
      accent: AppColors.sectorMetricAccent,
    ),
    PulseSectorCard(
      slug: 'future-finance',
      title: '미래 금융',
      score: 69,
      status: '관찰',
      accent: AppColors.sectorMetricAccent,
    ),
    PulseSectorCard(
      slug: 'next-gen-media',
      title: '콘텐츠 / IP',
      score: 64,
      status: '재정렬',
      accent: AppColors.sectorMetricAccent,
    ),
    PulseSectorCard(
      slug: 'smart-manufacturing',
      title: '지능형 제조',
      score: 78,
      status: '회복',
      accent: AppColors.sectorMetricAccent,
    ),
  ];

  static final Map<String, PulseSectorDetail> pulseDetailBySlug = {
    'ai-data': const PulseSectorDetail(
      headline: 'LLM·데이터 파이프라인·자동화가 동시에 가속화되는 구간입니다.',
      whyItMatters: [
        '생산성 도구가 ‘선택’이 아니라 ‘운영’으로 들어가며 채용/프로젝트가 빠르게 늘어납니다.',
        '보안·거버넌스 이슈가 같이 따라와 엔지니어링 난이도가 올라갑니다.',
      ],
      signals: [
        (label: '주간 속도 지수(예시)', value: '86 / 100'),
        (label: '핵심 키워드(예시)', value: 'RAG, Agent, MLOps'),
        (label: '채용/공고 신호(예시)', value: '백엔드·보안 직군 증가'),
      ],
      risks: [
        '기술 스택이 빠르게 갈아엎여 학습 부채가 누적될 수 있습니다.',
        '‘AI’라는 이름의 과대포장 공고가 섞일 수 있어 근거 확인이 필요합니다.',
      ],
    ),
    'sustainability-esg': const PulseSectorDetail(
      headline: '정책·자본·규제가 맞물리며 데이터 기반 의사결정 수요가 커집니다.',
      whyItMatters: [
        '배출·공급망 데이터의 투명성 요구가 강해지며 분석/감사 자동화가 핵심이 됩니다.',
        '대기업 규제 대응이 중소·파트너사로 전파되며 실무 프로젝트가 늘어납니다.',
      ],
      signals: [
        (label: '정책/규제 키워드(예시)', value: 'CBAM, 배출권, 공시'),
        (label: '산업 신호(예시)', value: '데이터 품질·감사 로그'),
        (label: '기회 직무(예시)', value: 'ESG 데이터·리스크 분석'),
      ],
      risks: [
        '데이터 소스가 분산되어 표준화/정합성 이슈가 크게 나타날 수 있습니다.',
        '규제 해석이 국가별로 달라 포트폴리오 설계가 어려울 수 있습니다.',
      ],
    ),
    'bio-health-tech': const PulseSectorDetail(
      headline: '디지털 헬스·바이오데이터·개인정보 보호가 동시에 중요해집니다.',
      whyItMatters: [
        '임상/운영 데이터의 품질과 보안이 제품 신뢰의 핵심 경쟁력이 됩니다.',
        '규제(의료기기/개인정보) 대응 역량이 엔지니어링에 직접 연결됩니다.',
      ],
      signals: [
        (label: '핵심 키워드(예시)', value: 'FHIR, EMR, Privacy'),
        (label: '수요 신호(예시)', value: '분석·보안·컴플라이언스'),
        (label: '협업 신호(예시)', value: '병원·제약·스타트업 파트너십'),
      ],
      risks: [
        '민감 데이터 취급으로 보안 사고 리스크가 큽니다.',
        '검증/인증 주기가 길어 POC→상용까지 시간이 걸릴 수 있습니다.',
      ],
    ),
    'future-finance': const PulseSectorDetail(
      headline: '금융의 디지털화는 ‘속도’보다 ‘신뢰(보안/컴플라이언스)’가 승패를 가릅니다.',
      whyItMatters: [
        '결제/정보보호/사기탐지가 기술 중심으로 재편되며 엔지니어 비중이 커집니다.',
        '규제 샌드박스·오픈뱅킹 등 환경 변화가 제품 로드맵에 직접 영향을 줍니다.',
      ],
      signals: [
        (label: '핵심 키워드(예시)', value: 'AML/KYC, 결제보안, 인증'),
        (label: '채용 신호(예시)', value: '백엔드·보안·데이터'),
        (label: '시장 신호(예시)', value: 'B2B 핀테크 인프라'),
      ],
      risks: [
        '규제 변화에 따른 리팩터링 비용이 큽니다.',
        '외부 공급자(카드/은행) 연동 이슈로 일정이 지연될 수 있습니다.',
      ],
    ),
    'next-gen-media': const PulseSectorDetail(
      headline: '콘텐츠는 ‘제작’에서 ‘유통·개인화·IP 비즈니스’로 이동 중입니다.',
      whyItMatters: [
        '플랫폼 알고리즘/권리/수익화가 결합되며 데이터 역량이 경쟁력이 됩니다.',
        '툴 체인(AI 생성·에디팅·분석)이 빠르게 진화합니다.',
      ],
      signals: [
        (label: '핵심 키워드(예시)', value: 'IP, 숏폼, 라이선스'),
        (label: '수요 신호(예시)', value: '기획·그로스·분석'),
        (label: '기술 신호(예시)', value: '추천/썸네일/자동편집'),
      ],
      risks: [
        '저작권/표절 이슈가 비즈니스 리스크로 직결됩니다.',
        '플랫폼 정책 변화에 따라 트래픽이 급변할 수 있습니다.',
      ],
    ),
    'smart-manufacturing': const PulseSectorDetail(
      headline: '공급망 리스크와 자동화가 겹치며 ‘현장 데이터’의 가치가 커집니다.',
      whyItMatters: [
        '설비/물류/품질 데이터를 실시간으로 다루는 SW 역량이 핵심입니다.',
        '로보틱스·비전·엣지가 결합되며 융합 인재 수요가 늘어납니다.',
      ],
      signals: [
        (label: '핵심 키워드(예시)', value: 'MES, SCADA, Digital Twin'),
        (label: '수요 신호(예시)', value: '엣지·OT 보안'),
        (label: '시장 신호(예시)', value: '리쇼어링/국산화'),
      ],
      risks: [
        'OT/IT 경계 문제로 보안 사고 영향이 큽니다.',
        '현장 도입은 PoC와 운영의 간극이 크기 쉽습니다.',
      ],
    ),
  };

  /// 블루오션 상단 칩용 짧은 라벨 (펄스 Top 6 슬러그와 대응).
  static const Map<String, String> gapSectorChipLabels = {
    'ai-data': '지능형 기술',
    'sustainability-esg': '지속 가능성',
    'bio-health-tech': '바이오·헬스',
    'future-finance': '미래 금융',
    'next-gen-media': '콘텐츠/IP',
    'smart-manufacturing': '지능형 제조',
  };

  static const List<GapIssueCard> gapIssues = [
    GapIssueCard(
      id: 'esg-market-transparency',
      sectorId: 'sustainability-esg',
      problem: '탄소 배출권 거래 시장의 데이터 투명성 부족',
      chance: 'ESG 데이터 분석가·감사 자동화 솔루션 수요 급증',
    ),
    GapIssueCard(
      id: 'enterprise-rag-quality',
      sectorId: 'ai-data',
      problem: '기업 LLM 도입 후 사내 지식검색(RAG) 품질 편차 확대',
      chance: 'RAG 엔지니어·검색 최적화 아키텍트 수요 증가',
    ),
    GapIssueCard(
      id: 'edge-ops-talent-gap',
      sectorId: 'smart-manufacturing',
      problem: '현장 OT/엣지 데이터·보안 운영 인력의 구조적 부족',
      chance: '산업 엣지·OT 보안·MES 연동 엔지니어 수요 확대',
    ),
    GapIssueCard(
      id: 'bio-emr-interop-gap',
      sectorId: 'bio-health-tech',
      problem: '병원·검사 데이터 상호운용(FHIR 등)과 거버넌스 비용 급증',
      chance: '헬스 데이터 엔지니어·개인정보 컴플라이언스 역할 수요 확대',
    ),
    GapIssueCard(
      id: 'future-finance-onchain-audit',
      sectorId: 'future-finance',
      problem: '스테이블코인·토큰화 자산의 실시간 감사·AML 데이터 표준 부재',
      chance: '온체인 리스크 분석·레포팅 자동화 스타트업·인력 수요',
    ),
    GapIssueCard(
      id: 'next-gen-media-ip-fragmentation',
      sectorId: 'next-gen-media',
      problem: '숏폼·리믹스 확산으로 IP 권리·수익 배분 추적이 어려워짐',
      chance: '권리 메타데이터·정산 자동화 도구·매니지먼트 인력 수요',
    ),
  ];

  /// `sectorId`가 null이면 전체 목록.
  static List<GapIssueCard> gapIssuesForSector(String? sectorId) {
    if (sectorId == null) return List<GapIssueCard>.from(gapIssues);
    return gapIssues.where((c) => c.sectorId == sectorId).toList();
  }

  static final Map<String, GapIssueDetail> gapDetailById = {
    'esg-market-transparency': const GapIssueDetail(
      id: 'esg-market-transparency',
      sectorId: 'sustainability-esg',
      problem: '탄소 배출권 거래 시장의 데이터 투명성 부족',
      chance: 'ESG 데이터 분석가·감사 자동화 솔루션 수요 급증',
      summary:
          '배출권·공급망 데이터의 신뢰성이 확보되지 않으면 기업의 감사·공시·거래 비용이 폭증합니다. 데이터 파이프라인과 검증(계측/로그)이 핵심 경쟁력이 됩니다.',
      stakeholders: ['ESG/컴플라이언스', '데이터 엔지니어링', '감사(내부회계)', '공급망 운영'],
      nextSteps: [
        '데이터 소스(ERP/SCM/IoT) 목록화와 품질 지표 정의',
        '감사 추적 가능한 파이프라인(버전/출처) 설계',
        'PoC 범위를 ‘보고’가 아니라 ‘자동 검증’으로 좁히기',
      ],
    ),
    'enterprise-rag-quality': const GapIssueDetail(
      id: 'enterprise-rag-quality',
      sectorId: 'ai-data',
      problem: '기업 LLM 도입 후 사내 지식검색(RAG) 품질 편차 확대',
      chance: 'RAG 엔지니어·검색 최적화 아키텍트 수요 증가',
      summary:
          'RAG는 도입이 쉬워 보이지만, 청킹·임베딩·재랭킹·권한/보안·평가루프가 어긋나면 품질이 급락합니다. ‘검색 품질 엔지니어링’이 별도 직무로 분리되는 흐름이 강해집니다.',
      stakeholders: ['플랫폼 엔지니어', '보안', '지식관리(KM)', '법무/컴플라이언스'],
      nextSteps: [
        '문서 권한 모델(부서/기밀)과 검색 결과 노출 정책 정리',
        '오프라인 평가셋(질문-정답 근거) 구축',
        '재현 가능한 배포/롤백(모델/인덱스) 파이프라인 만들기',
      ],
    ),
    'edge-ops-talent-gap': const GapIssueDetail(
      id: 'edge-ops-talent-gap',
      sectorId: 'smart-manufacturing',
      problem: '현장 OT/엣지 데이터·보안 운영 인력의 구조적 부족',
      chance: '산업 엣지·OT 보안·MES 연동 엔지니어 수요 확대',
      summary:
          '제조·에너지·유통의 현장은 IT와 OT가 섞이며, 관측·제어·보안이 동시에 요구됩니다. ‘클라우드만 아는’ 인력으로는 엣지·OT 가시성을 확보하기 어려워집니다.',
      stakeholders: ['OT/엣지 엔지니어', '보안(OT·IT)', '생산/설비', 'SI 파트너'],
      nextSteps: [
        '자산(PLC/센서/게이트웨이) 인벤토리와 네트워크 구획 정리',
        '엣지 수집·스토리지·알람의 최소 가용 PoC(1라인) 정의',
        'OT 보안(세그멘테이션, 계정, 패치) 기준 수립',
      ],
    ),
    'bio-emr-interop-gap': const GapIssueDetail(
      id: 'bio-emr-interop-gap',
      sectorId: 'bio-health-tech',
      problem: '병원·검사 데이터 상호운용(FHIR 등)과 거버넌스 비용 급증',
      chance: '헬스 데이터 엔지니어·개인정보 컴플라이언스 역할 수요 확대',
      summary:
          '의료기관·파트너 간 데이터 교환이 늘면서 스키마 정합, 동의/최소수집, 감사 로그 요구가 함께 커집니다. ‘연결’만이 아니라 ‘증명 가능한 거버넌스’가 경쟁력이 됩니다.',
      stakeholders: ['헬스 IT', '임상·품질', '보안', '법무/컴플라이언스'],
      nextSteps: [
        'FHIR 리소스 범위와 동의 정책(목적·보존) 정리',
        '비식별·접근통제에 대한 테스트 데이터셋 확보',
        '감사 추적(누가 어떤 목적으로 조회했는지) 최소 설계',
      ],
    ),
    'future-finance-onchain-audit': const GapIssueDetail(
      id: 'future-finance-onchain-audit',
      sectorId: 'future-finance',
      problem: '스테이블코인·토큰화 자산의 실시간 감사·AML 데이터 표준 부재',
      chance: '온체인 리스크 분석·레포팅 자동화 스타트업·인력 수요',
      summary:
          '온체인 거래는 투명해 보이지만, 오프램프·혼합 지갑·크로스체인까지 포함하면 관측·분류가 어렵습니다. 규제 대응 가능한 데이터 모델·리포트가 별도 역량으로 자리잡습니다.',
      stakeholders: ['리스크/컴플라이언스', '데이터 엔지니어', '감사', '파트너 은행'],
      nextSteps: [
        '자산 유형별(스테이블/증권형 토큰) 요구 규칙 목록화',
        '주소·거래 클러스터링 PoC와 오탐 검토 프로세스',
        '감사 로그·보고서 템플릿을 규제 FAQ와 매핑',
      ],
    ),
    'next-gen-media-ip-fragmentation': const GapIssueDetail(
      id: 'next-gen-media-ip-fragmentation',
      sectorId: 'next-gen-media',
      problem: '숏폼·리믹스 확산으로 IP 권리·수읡 배분 추적이 어려워짐',
      chance: '권리 메타데이터·정산 자동화 도구·매니지먼트 인력 수요',
      summary:
          '플랫폼별 조건과 UGC 리믹스가 겹치며 권리 주장이 분산됩니다. 크리에이터·레이블·브랜드 모두 ‘근거 있는 정산’을 원하게 되며 도구와 운영 인력이 함께 필요합니다.',
      stakeholders: ['크리에이터/레이블', '플랫폼', '법무', '데이터/ML'],
      nextSteps: [
        '콘텐츠 ID·라이선스 메타데이터 최소 스키마 정의',
        '샘플 계약(2차 저작·리믹스)과 정산 주기 정리',
        '탐지·분쟁 대응을 위한 증거(타임스탬프·출처) 확보 절차',
      ],
    ),
  };

  static const List<ChanceCard> chanceCards = [
    ChanceCard(
      id: 'youth-ai-hackathon-2026',
      title: '2026 청년 AI 혁신 공모전',
      type: '공모전',
      dday: 'D-3',
      match: 85,
    ),
    ChanceCard(
      id: 'ai-bootcamp-7',
      title: 'AI 인재 양성 부트캠프 7기',
      type: '교육',
      dday: 'D-6',
      match: 78,
    ),
    ChanceCard(
      id: 'esg-data-internship',
      title: 'ESG 데이터 분석 인턴십',
      type: '채용',
      dday: 'D-10',
      match: 82,
    ),
  ];

  static final Map<String, ChanceDetail> chanceDetailById = {
    'youth-ai-hackathon-2026': const ChanceDetail(
      id: 'youth-ai-hackathon-2026',
      title: '2026 청년 AI 혁신 공모전',
      type: '공모전',
      dday: 'D-3',
      match: 85,
      summary:
          '팀 빌딩·문제정의·프로토타입까지 빠르게 돌려야 하는 형식입니다. 백엔드/데이터 기반이 있으면 ‘현장 문제 → 데모’로 연결하기 좋습니다.',
      eligibility: [
        '청년(연령 기준은 공고문 확인)',
        '팀 또는 개인 참가 규정 확인',
        '제출물 형식(PDF/영상/깃허브) 준수',
      ],
      prepare: [
        '아이디어 1p(문제/고객/가설/지표) 정리',
        '데모 범위를 48시간 내 완성 가능한 크기로 축소',
        '발표 스토리라인(왜 지금인가) 작성',
      ],
    ),
    'ai-bootcamp-7': const ChanceDetail(
      id: 'ai-bootcamp-7',
      title: 'AI 인재 양성 부트캠프 7기',
      type: '교육',
      dday: 'D-6',
      match: 78,
      summary:
          '짧은 기간에 실무 프로젝트 중심으로 커리큘럼이 압축됩니다. 선발에서 기초 역량(파이썬/깃/HTTP)과 학습 태도를 강하게 봅니다.',
      eligibility: ['지원 자격(학력/경력) 공고 확인', '사전 과제 여부 확인', '시간 풀타임 가능 여부'],
      prepare: [
        'Python 기본기 + 간단한 API 서버 과제 1개',
        '포트폴리오 README에 문제/결과/회고 구조화',
        '면접에서 말할 ‘학습 계획 30일’ 준비',
      ],
    ),
    'esg-data-internship': const ChanceDetail(
      id: 'esg-data-internship',
      title: 'ESG 데이터 분석 인턴십',
      type: '채용',
      dday: 'D-10',
      match: 82,
      summary:
          'ESG 데이터는 정의가 흔들리기 쉬워, ‘지표를 어떻게 만들고 검증할지’가 핵심입니다. SQL/대시보드/감사 로그에 강점이 있으면 매칭이 좋아집니다.',
      eligibility: ['데이터 분석 경험(학교 과제/프로젝트 포함)', 'SQL 필수 여부 확인', '근무 지역/일정 확인'],
      prepare: [
        'KPI 정의서 템플릿(문제-지표-데이터-검증) 1건 작성',
        '샘플 데이터로 대시보드 1장 만들기',
        '개인정보/저작권 이슈 체크리스트 정리',
      ],
    ),
  };

  static const SyncOverviewMock syncOverview = SyncOverviewMock(
    score: 72,
    deltaWeek: 4,
    topTrends: ['AI & Data', 'Sustainability & ESG', 'Future Finance'],
    reasonLines: [
      '상담실에서 저장한 키워드와 최근 7일 펄스 키워드가 부분적으로 겹칩니다.',
      '데이터·보안 직군 공고 노출이 증가해 역량 스택과 방향이 맞습니다.',
      '관심 도메인(ESG)과 찜한 블루오션 이슈가 싱크 가중치에 반영되었습니다.',
    ],
    keywordEvidence: '키워드 12 · 역량 태그 5 · 데이터 출처 4건',
  );

  static PulseSectorCard? sectorBySlug(String slug) {
    for (final s in pulseSectors) {
      if (s.slug == slug) return s;
    }
    return null;
  }

  static PulseSectorDetail? pulseDetail(String slug) => pulseDetailBySlug[slug];

  static GapIssueDetail? gapDetail(String id) => gapDetailById[id];

  static ChanceDetail? chanceDetail(String id) => chanceDetailById[id];
}
