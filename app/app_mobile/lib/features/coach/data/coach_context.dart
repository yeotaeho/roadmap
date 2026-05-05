// 웹 `src/data/coachContext.ts` 와 동일 — 데모 맥락·액티브 포커스 (추후 API 치환)

class CoachAttachedContext {
  const CoachAttachedContext({
    required this.id,
    required this.source,
    required this.label,
  });

  final String id;
  final String source; // chance | roadmap | pulse
  final String label;
}

class CoachWalletItem {
  const CoachWalletItem({
    required this.id,
    required this.title,
    required this.body,
    required this.createdAt,
  });

  final String id;
  final String title;
  final String body;
  final int createdAt;
}

/// 우측 Active Context 카드 (로드맵 연동 요약)
class CoachActiveFocus {
  const CoachActiveFocus({
    required this.title,
    required this.subtitle,
    required this.body,
    required this.tags,
  });

  final String title;
  final String subtitle;
  final String body;
  final List<String> tags;
}

const Map<String, CoachAttachedContext> demoAttachedContexts = {
  'chance': CoachAttachedContext(
    id: 'ctx-chance-1',
    source: 'chance',
    label:
        '그린테크 스타트업 백엔드 엔지니어 채용 (필수: 대용량 데이터 파이프라인, 우대: ESG 공시 이해도)',
  ),
  'roadmap': CoachAttachedContext(
    id: 'ctx-roadmap-1',
    source: 'roadmap',
    label: '진행 중인 퀘스트: 탄소 배출 룰 기반 계산 엔진 · 스키마·가중치 모듈 분리',
  ),
};

const CoachActiveFocus coachActiveFocus = CoachActiveFocus(
  title: '현재 집중 목표',
  subtitle: 'IFRS S1/S2 데이터 맵핑',
  body:
      '탄소 배출 룰 기반 계산 엔진 — 스키마 단계에서 엔티티 경계와 가중치 정책을 분리해 두면 이후 파이프라인·공시 매핑까지 확장하기 쉽습니다.',
  tags: ['FastAPI', 'PostgreSQL', 'ESG 공시', '파이프라인'],
);
