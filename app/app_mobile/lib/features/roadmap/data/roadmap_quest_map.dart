// 웹 `src/data/roadmapQuestMap.ts` 와 동일 — 여정 개요·성장 아카이브 공통 소스.

class SkillPillar {
  const SkillPillar({
    required this.id,
    required this.label,
    required this.blurb,
  });

  final String id;
  final String label;
  final String blurb;
}

/// 스킬 트라이앵글 — 핵심 3축
const List<SkillPillar> skillTriangle = [
  SkillPillar(
    id: 'pillar-data',
    label: '데이터 파이프라인',
    blurb: '수집·정제·저장까지 신뢰 가능한 흐름 설계',
  ),
  SkillPillar(
    id: 'pillar-domain',
    label: '에너지·ESG 도메인',
    blurb: '규제·지표·비즈니스 맥락을 언어로 전환',
  ),
  SkillPillar(
    id: 'pillar-ai',
    label: 'AI 엔지니어링',
    blurb: '모델보다 시스템 — 배포·관측·품질',
  ),
];

/// 직무 키워드 브릿지 (대시보드·상담실과의 연결 앵커)
const List<String> bridgeKeywords = [
  '탄소회계',
  'CSRD',
  'FastAPI',
  '관측 가능성',
  '포트폴리오 스토리',
];

typedef QuestDifficulty = String; // 입문 | 중급 | 심화
typedef QuestTreeState = String; // start | available | active | done | locked

class QuestTreeNode {
  const QuestTreeNode({
    required this.id,
    required this.title,
    required this.purpose,
    required this.difficulty,
    required this.keywords,
    required this.state,
    this.children,
  });

  final String id;
  final String title;
  final String purpose;
  final QuestDifficulty difficulty;
  final List<String> keywords;
  final QuestTreeState state;
  final List<QuestTreeNode>? children;
}

/// RPG 스킬 트리 형태의 퀘스트 맵 (일정 강제 없이 ‘풍경’)
const QuestTreeNode questTree = QuestTreeNode(
  id: 'root',
  title: '나의 시작점',
  purpose: '대시보드·상담에서 도출된 간극을 바탕으로, 지금 서 있는 위치입니다.',
  difficulty: '입문',
  keywords: ['현재 위치', '간극 인식'],
  state: 'start',
  children: [
    QuestTreeNode(
      id: 'q-esg-map',
      title: 'ESG 데이터 지형도 그리기',
      purpose:
          '공개 데이터·지표 체계를 한 장의 지도로 정리해 도메인 언어를 몸에 익힙니다.',
      difficulty: '입문',
      keywords: ['지표', '데이터 소스', '용어'],
      state: 'done',
      children: [
        QuestTreeNode(
          id: 'q-carbon-schema',
          title: '탄소 데이터 스키마 초안',
          purpose:
              '배출·감축 데이터가 어떤 엔티티로 흐르는지 스키마로 고정합니다.',
          difficulty: '중급',
          keywords: ['스키마', '엔티티', '갭'],
          state: 'active',
        ),
        QuestTreeNode(
          id: 'q-pipeline-mini',
          title: '데이터 파이프라인 미니 구현',
          purpose:
              '입력→검증→저장의 최소 파이프라인으로 ‘움직이는 증거’를 만듭니다.',
          difficulty: '심화',
          keywords: ['FastAPI', 'ETL', '품질'],
          state: 'available',
          children: [
            QuestTreeNode(
              id: 'q-observability',
              title: '관측·재처리 루프',
              purpose:
                  '실패를 전제로 로그·알림·재시도를 설계해 운영 감각을 쌓습니다.',
              difficulty: '심화',
              keywords: ['로그', 'SLA', '재처리'],
              state: 'locked',
            ),
          ],
        ),
      ],
    ),
    QuestTreeNode(
      id: 'q-portfolio-case',
      title: '도메인 문제 해결형 포트폴리오',
      purpose:
          '실제 결핍을 정의하고, 코드·문서·데모로 ‘해결의 궤적’을 남깁니다.',
      difficulty: '중급',
      keywords: ['케이스', 'README', '데모'],
      state: 'available',
      children: [
        QuestTreeNode(
          id: 'q-story-pitch',
          title: '면접 스토리라인 (3분 피치)',
          purpose: '문제-실행-성과를 한 호흡으로 말할 수 있게 구조화합니다.',
          difficulty: '중급',
          keywords: ['STAR', '임팩트', '피치'],
          state: 'locked',
        ),
      ],
    ),
  ],
);

class QuestTitleEntry {
  const QuestTitleEntry({required this.id, required this.title});

  final String id;
  final String title;
}

List<QuestTitleEntry> flattenQuestTitles(QuestTreeNode node) {
  final out = <QuestTitleEntry>[QuestTitleEntry(id: node.id, title: node.title)];
  for (final ch in node.children ?? const <QuestTreeNode>[]) {
    out.addAll(flattenQuestTitles(ch));
  }
  return out;
}

/// 아카이브 달력 시드 — 점 표시·일별 로그 목업
class DayLog {
  const DayLog({
    this.completedQuestIds = const [],
    this.note = '',
  });

  final List<String> completedQuestIds;
  final String note;

  DayLog copyWith({
    List<String>? completedQuestIds,
    String? note,
  }) {
    return DayLog(
      completedQuestIds: completedQuestIds ?? this.completedQuestIds,
      note: note ?? this.note,
    );
  }
}

/// 웹 `ARCHIVE_ACTIVITY_SEED` 동일
final Map<String, DayLog> archiveActivitySeed = {
  '2026-04-22': DayLog(
    completedQuestIds: ['q-esg-map'],
    note: '공공 API 2종 정리, 지표 용어집 초안 작성.',
  ),
  '2026-04-26': DayLog(
    completedQuestIds: ['q-esg-map'],
    note: 'ESG 리포트 샘플 읽고 질문 리스트업.',
  ),
};
