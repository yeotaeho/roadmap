import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../core/theme/app_colors.dart';
import '../data/roadmap_quest_map.dart';

/// 전략 로드맵 — 웹 `RoadmapView` / `JourneyMapTab` / `GrowthArchiveTab` 에 맞춘 모바일 IA.
class RoadmapPage extends StatefulWidget {
  const RoadmapPage({super.key});

  @override
  State<RoadmapPage> createState() => _RoadmapPageState();
}

class _RoadmapPageState extends State<RoadmapPage>
    with SingleTickerProviderStateMixin {
  late final TabController _tabController;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.slate950,
      appBar: AppBar(
        backgroundColor: AppColors.slate950,
        surfaceTintColor: Colors.transparent,
        title: const Text('전략 로드맵'),
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
            child: _RoadmapSubTabBar(
              tabController: _tabController,
            ),
          ),
          Expanded(
            child: TabBarView(
              controller: _tabController,
              children: const [
                _JourneyMapBody(),
                _GrowthArchiveBody(),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

// —— 서브탭 (웹 `nav` 세그먼트) ————————————————————————————————

class _RoadmapSubTabBar extends StatelessWidget {
  const _RoadmapSubTabBar({required this.tabController});

  final TabController tabController;

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: tabController,
      builder: (context, _) {
        final i = tabController.index;
        return Container(
          padding: const EdgeInsets.all(4),
          decoration: BoxDecoration(
            color: AppColors.slate900,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: AppColors.slate700),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withValues(alpha: 0.2),
                blurRadius: 8,
                offset: const Offset(0, 2),
              ),
            ],
          ),
          child: Row(
            children: [
              Expanded(
                child: _SubTabPill(
                  label: '여정 개요',
                  hint: 'Journey Map',
                  selected: i == 0,
                  onTap: () => tabController.animateTo(0),
                ),
              ),
              const SizedBox(width: 4),
              Expanded(
                child: _SubTabPill(
                  label: '성장 아카이브',
                  hint: 'Growth Calendar',
                  selected: i == 1,
                  onTap: () => tabController.animateTo(1),
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}

class _SubTabPill extends StatelessWidget {
  const _SubTabPill({
    required this.label,
    required this.hint,
    required this.selected,
    required this.onTap,
  });

  final String label;
  final String hint;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 200),
          padding: const EdgeInsets.symmetric(vertical: 10, horizontal: 8),
          decoration: BoxDecoration(
            color: selected ? AppColors.slate800 : Colors.transparent,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(
              color: selected ? AppColors.slate700 : Colors.transparent,
            ),
            boxShadow: selected
                ? [
                    BoxShadow(
                      color: Colors.black.withValues(alpha: 0.15),
                      blurRadius: 4,
                      offset: const Offset(0, 1),
                    ),
                  ]
                : null,
          ),
          child: Stack(
            alignment: Alignment.bottomCenter,
            children: [
              Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    label,
                    textAlign: TextAlign.center,
                    style: Theme.of(context).textTheme.labelLarge?.copyWith(
                          fontWeight: FontWeight.w800,
                          color: selected
                              ? scheme.onSurface
                              : scheme.onSurfaceVariant,
                        ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    hint,
                    textAlign: TextAlign.center,
                    style: Theme.of(context).textTheme.labelSmall?.copyWith(
                          fontSize: 10,
                          color: scheme.onSurfaceVariant
                              .withValues(alpha: 0.85),
                        ),
                  ),
                ],
              ),
              if (selected)
                Positioned(
                  bottom: 0,
                  left: 12,
                  right: 12,
                  child: Container(
                    height: 2,
                    decoration: BoxDecoration(
                      color: AppColors.indigo600,
                      borderRadius: BorderRadius.circular(999),
                    ),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

// —— 여정 개요 (JourneyMapTab) ————————————————————————————————

class _JourneyMapBody extends StatelessWidget {
  const _JourneyMapBody();

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 0, 16, 24),
      children: const [
        _PageIntroBlock(),
        SizedBox(height: 16),
        _SkillTriangleSection(),
        SizedBox(height: 16),
        _KeywordBridgeSection(),
        SizedBox(height: 16),
        _QuestTreeSection(),
        SizedBox(height: 20),
        _NextActionsSection(),
      ],
    );
  }
}

class _PageIntroBlock extends StatelessWidget {
  const _PageIntroBlock();

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: AppColors.indigo600.withValues(alpha: 0.2),
            borderRadius: BorderRadius.circular(12),
          ),
          child: Icon(Icons.route_rounded, color: AppColors.indigo600, size: 26),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text.rich(
                TextSpan(
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: scheme.onSurfaceVariant,
                        height: 1.45,
                      ),
                  children: [
                    const TextSpan(text: '일정 감시가 아니라, '),
                    TextSpan(
                      text: '기회(퀘스트) 지도',
                      style: TextStyle(
                        fontWeight: FontWeight.w600,
                        color: scheme.onSurface,
                      ),
                    ),
                    const TextSpan(text: '와 '),
                    TextSpan(
                      text: '성장 기록',
                      style: TextStyle(
                        fontWeight: FontWeight.w600,
                        color: scheme.onSurface,
                      ),
                    ),
                    const TextSpan(text: '을 나란히 둡니다.'),
                  ],
                ),
              ),
              const SizedBox(height: 6),
              Text(
                '목표 브릿지: 에너지·ESG × AI 엔지니어링 (방향만 고정, 마감은 강제하지 않음)',
                style: Theme.of(context).textTheme.labelSmall?.copyWith(
                      color: scheme.onSurfaceVariant.withValues(alpha: 0.9),
                      height: 1.35,
                    ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _SkillTriangleSection extends StatelessWidget {
  const _SkillTriangleSection();

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.slate900,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.slate700),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            '스킬 트라이앵글',
            style: Theme.of(context).textTheme.labelSmall?.copyWith(
                  fontWeight: FontWeight.w800,
                  letterSpacing: 0.6,
                  color: scheme.onSurfaceVariant,
                ),
          ),
          const SizedBox(height: 6),
          Text(
            '획득해야 할 핵심 3축입니다. 일정이 아니라 역량 방향을 먼저 고정합니다.',
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: scheme.onSurfaceVariant,
                  height: 1.4,
                ),
          ),
          const SizedBox(height: 16),
          SizedBox(
            height: 220,
            child: Stack(
              alignment: Alignment.center,
              children: [
                Positioned(
                  top: 0,
                  left: 0,
                  right: 0,
                  child: Center(
                    child: _PillarCard(
                      pillar: skillTriangle[0],
                      maxWidth: 148,
                    ),
                  ),
                ),
                Positioned(
                  bottom: 0,
                  left: 0,
                  child: _PillarCard(
                    pillar: skillTriangle[1],
                    maxWidth: 148,
                  ),
                ),
                Positioned(
                  bottom: 0,
                  right: 0,
                  child: _PillarCard(
                    pillar: skillTriangle[2],
                    maxWidth: 148,
                  ),
                ),
                Center(
                  child: Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 14,
                      vertical: 10,
                    ),
                    decoration: BoxDecoration(
                      color: AppColors.slate800,
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(
                        color: AppColors.indigo600.withValues(alpha: 0.45),
                      ),
                      boxShadow: [
                        BoxShadow(
                          color: AppColors.indigo600.withValues(alpha: 0.12),
                          blurRadius: 12,
                        ),
                      ],
                    ),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(
                          Icons.change_history_rounded,
                          size: 22,
                          color: AppColors.indigo600,
                        ),
                        const SizedBox(height: 4),
                        Text(
                          'YOU',
                          style: Theme.of(context).textTheme.labelSmall?.copyWith(
                                fontWeight: FontWeight.w800,
                                color: AppColors.indigo600,
                              ),
                        ),
                        Text(
                          '지금 여기',
                          style: Theme.of(context).textTheme.labelSmall?.copyWith(
                                fontSize: 10,
                                color: scheme.onSurfaceVariant,
                              ),
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _PillarCard extends StatelessWidget {
  const _PillarCard({
    required this.pillar,
    required this.maxWidth,
  });

  final SkillPillar pillar;
  final double maxWidth;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return ConstrainedBox(
      constraints: BoxConstraints(maxWidth: maxWidth),
      child: Container(
        padding: const EdgeInsets.all(10),
        decoration: BoxDecoration(
          color: AppColors.slate800,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: AppColors.slate700),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.12),
              blurRadius: 6,
              offset: const Offset(0, 2),
            ),
          ],
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(Icons.hexagon_outlined, size: 16, color: AppColors.indigo600),
            const SizedBox(height: 6),
            Text(
              pillar.label,
              style: Theme.of(context).textTheme.labelLarge?.copyWith(
                    fontWeight: FontWeight.w800,
                    color: scheme.onSurface,
                  ),
            ),
            const SizedBox(height: 4),
            Text(
              pillar.blurb,
              style: Theme.of(context).textTheme.labelSmall?.copyWith(
                    color: scheme.onSurfaceVariant,
                    height: 1.35,
                  ),
            ),
          ],
        ),
      ),
    );
  }
}

class _KeywordBridgeSection extends StatelessWidget {
  const _KeywordBridgeSection();

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.slate800,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.slate700),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            '직무 키워드 브릿지',
            style: Theme.of(context).textTheme.labelSmall?.copyWith(
                  fontWeight: FontWeight.w600,
                  color: scheme.onSurfaceVariant,
                ),
          ),
          const SizedBox(height: 6),
          Text(
            '대시보드 트렌드와 상담 결과를 잇는 태그입니다.',
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: scheme.onSurfaceVariant,
                  height: 1.4,
                ),
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: bridgeKeywords
                .map(
                  (k) => Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 12,
                      vertical: 8,
                    ),
                    decoration: BoxDecoration(
                      color: AppColors.indigo600.withValues(alpha: 0.15),
                      borderRadius: BorderRadius.circular(999),
                      border: Border.all(
                        color: AppColors.indigo600.withValues(alpha: 0.35),
                      ),
                    ),
                    child: Text(
                      k,
                      style: Theme.of(context).textTheme.labelMedium?.copyWith(
                            fontWeight: FontWeight.w700,
                            color: AppColors.indigo600,
                          ),
                    ),
                  ),
                )
                .toList(),
          ),
        ],
      ),
    );
  }
}

class _QuestTreeSection extends StatelessWidget {
  const _QuestTreeSection();

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.slate800,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.slate700),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.15),
            blurRadius: 10,
            offset: const Offset(0, 3),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            '퀘스트 트리',
            style: Theme.of(context).textTheme.labelSmall?.copyWith(
                  fontWeight: FontWeight.w800,
                  letterSpacing: 0.6,
                  color: scheme.onSurfaceVariant,
                ),
          ),
          const SizedBox(height: 4),
          Text(
            '과제 맵 (Quest Tree)',
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.w800,
                  color: scheme.onSurface,
                ),
          ),
          const SizedBox(height: 6),
          Text(
            '시작점에서 가지처럼 퍼지는 과제들입니다. 잠금(회색)은 앞 단계를 밟으면 열립니다.',
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: scheme.onSurfaceVariant,
                  height: 1.4,
                ),
          ),
          const SizedBox(height: 16),
          _QuestTreeCard(node: questTree, depth: 0),
        ],
      ),
    );
  }
}

class _QuestTreeCard extends StatelessWidget {
  const _QuestTreeCard({
    required this.node,
    required this.depth,
  });

  final QuestTreeNode node;
  final int depth;

  static BoxDecoration _cardDecoration(String state) {
    switch (state) {
      case 'start':
        return BoxDecoration(
          color: AppColors.indigo600.withValues(alpha: 0.12),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: AppColors.indigo600.withValues(alpha: 0.55)),
          boxShadow: [
            BoxShadow(
              color: AppColors.indigo600.withValues(alpha: 0.15),
              blurRadius: 10,
            ),
          ],
        );
      case 'done':
        return BoxDecoration(
          color: AppColors.slate800,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: const Color(0xFF34D399).withValues(alpha: 0.45)),
        );
      case 'active':
        return BoxDecoration(
          color: AppColors.slate800,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: AppColors.indigo600.withValues(alpha: 0.65), width: 1.5),
          boxShadow: [
            BoxShadow(
              color: AppColors.indigo600.withValues(alpha: 0.12),
              blurRadius: 8,
            ),
          ],
        );
      case 'locked':
        return BoxDecoration(
          color: AppColors.slate900.withValues(alpha: 0.65),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: AppColors.slate700),
        );
      default:
        return BoxDecoration(
          color: AppColors.slate800,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: AppColors.slate700),
        );
    }
  }

  static Color _difficultyFg(String d) {
    switch (d) {
      case '입문':
        return const Color(0xFF34D399);
      case '중급':
        return const Color(0xFFFBBF24);
      case '심화':
        return const Color(0xFFC4B5FD);
      default:
        return Colors.white70;
    }
  }

  static Color _difficultyBg(String d) {
    switch (d) {
      case '입문':
        return const Color(0xFF34D399).withValues(alpha: 0.12);
      case '중급':
        return const Color(0xFFFBBF24).withValues(alpha: 0.12);
      case '심화':
        return const Color(0xFFA78BFA).withValues(alpha: 0.15);
      default:
        return AppColors.slate700;
    }
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final isRoot = node.state == 'start';
    final locked = node.state == 'locked';

    final column = Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Opacity(
          opacity: locked ? 0.72 : 1,
          child: Container(
            padding: const EdgeInsets.all(14),
            decoration: _cardDecoration(node.state),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            node.title,
                            style: Theme.of(context).textTheme.titleSmall?.copyWith(
                                  fontWeight: FontWeight.w800,
                                  color: scheme.onSurface,
                                ),
                          ),
                          const SizedBox(height: 6),
                          Text(
                            node.purpose,
                            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                                  color: scheme.onSurfaceVariant,
                                  height: 1.4,
                                ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(width: 8),
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.end,
                      children: [
                        Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 8,
                            vertical: 4,
                          ),
                          decoration: BoxDecoration(
                            color: _difficultyBg(node.difficulty),
                            borderRadius: BorderRadius.circular(999),
                            border: Border.all(
                              color: _difficultyFg(node.difficulty)
                                  .withValues(alpha: 0.45),
                            ),
                          ),
                          child: Text(
                            node.difficulty,
                            style: Theme.of(context).textTheme.labelSmall?.copyWith(
                                  fontWeight: FontWeight.w800,
                                  fontSize: 10,
                                  color: _difficultyFg(node.difficulty),
                                ),
                          ),
                        ),
                        if (isRoot) ...[
                          const SizedBox(height: 6),
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 8,
                              vertical: 4,
                            ),
                            decoration: BoxDecoration(
                              color: AppColors.indigo600.withValues(alpha: 0.2),
                              borderRadius: BorderRadius.circular(999),
                            ),
                            child: Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                Icon(
                                  Icons.auto_awesome,
                                  size: 12,
                                  color: AppColors.indigo600,
                                ),
                                const SizedBox(width: 4),
                                Text(
                                  '시작점',
                                  style: Theme.of(context)
                                      .textTheme
                                      .labelSmall
                                      ?.copyWith(
                                        fontWeight: FontWeight.w700,
                                        fontSize: 10,
                                        color: AppColors.indigo600,
                                      ),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ],
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                Wrap(
                  spacing: 6,
                  runSpacing: 6,
                  children: node.keywords
                      .map(
                        (kw) => Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 8,
                            vertical: 4,
                          ),
                          decoration: BoxDecoration(
                            color: AppColors.slate900.withValues(alpha: 0.55),
                            borderRadius: BorderRadius.circular(999),
                          ),
                          child: Text(
                            '#$kw',
                            style: Theme.of(context).textTheme.labelSmall?.copyWith(
                                  fontWeight: FontWeight.w600,
                                  color: scheme.onSurfaceVariant,
                                ),
                          ),
                        ),
                      )
                      .toList(),
                ),
              ],
            ),
          ),
        ),
        if (node.children != null && node.children!.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(left: 12, top: 10),
            child: Container(
              padding: const EdgeInsets.only(left: 10),
              decoration: BoxDecoration(
                border: Border(
                  left: BorderSide(color: AppColors.slate700, width: 2),
                ),
              ),
              child: Column(
                children: node.children!
                    .map(
                      (ch) => Padding(
                        padding: const EdgeInsets.only(bottom: 10),
                        child: _QuestTreeCard(node: ch, depth: depth + 1),
                      ),
                    )
                    .toList(),
              ),
            ),
          ),
      ],
    );

    return column;
  }
}

class _NextActionsSection extends StatelessWidget {
  const _NextActionsSection();

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.slate900,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.slate700),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.explore_outlined, size: 18, color: AppColors.indigo600),
              const SizedBox(width: 8),
              Text(
                '다음 액션',
                style: Theme.of(context).textTheme.labelLarge?.copyWith(
                      fontWeight: FontWeight.w800,
                      color: scheme.onSurface,
                    ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              _NextActionChip(
                label: 'AI 상담실',
                emphasis: true,
                onTap: () => context.go('/consult'),
              ),
              _NextActionChip(
                label: 'AI 코치',
                emphasis: false,
                onTap: () => context.go('/coach'),
              ),
              _NextActionChip(
                label: '인사이트 대시보드',
                emphasis: false,
                onTap: () => context.go('/'),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _NextActionChip extends StatelessWidget {
  const _NextActionChip({
    required this.label,
    required this.emphasis,
    required this.onTap,
  });

  final String label;
  final bool emphasis;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
          decoration: BoxDecoration(
            color: emphasis
                ? AppColors.indigo600.withValues(alpha: 0.18)
                : AppColors.slate800,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(
              color: emphasis
                  ? AppColors.indigo600.withValues(alpha: 0.45)
                  : AppColors.slate700,
            ),
          ),
          child: Text(
            label,
            style: Theme.of(context).textTheme.labelLarge?.copyWith(
                  fontWeight: FontWeight.w700,
                  color: emphasis ? AppColors.indigo600 : Theme.of(context).colorScheme.onSurfaceVariant,
                ),
          ),
        ),
      ),
    );
  }
}

// —— 성장 아카이브 (GrowthArchiveTab) ——————————————————————————

class _GrowthArchiveBody extends StatefulWidget {
  const _GrowthArchiveBody();

  @override
  State<_GrowthArchiveBody> createState() => _GrowthArchiveBodyState();
}

class _GrowthArchiveBodyState extends State<_GrowthArchiveBody> {
  late Map<String, DayLog> _logs;
  late String _selectedKey;
  late final TextEditingController _noteController;
  final _today = DateTime.now();

  static const _weekLabels = ['일', '월', '화', '수', '목', '금', '토'];

  int _monthOffset = 0;

  @override
  void initState() {
    super.initState();
    _logs = {
      for (final e in archiveActivitySeed.entries)
        e.key: DayLog(
          completedQuestIds: List<String>.from(e.value.completedQuestIds),
          note: e.value.note,
        ),
    };
    _selectedKey = _toKey(DateTime(_today.year, _today.month, _today.day));
    _noteController = TextEditingController(text: _logFor(_selectedKey).note);
  }

  @override
  void dispose() {
    _noteController.dispose();
    super.dispose();
  }

  void _selectDay(String key) {
    setState(() {
      _selectedKey = key;
      final n = _logFor(_selectedKey).note;
      _noteController.value = TextEditingValue(
        text: n,
        selection: TextSelection.collapsed(offset: n.length),
      );
    });
  }

  String _toKey(DateTime d) =>
      '${d.year}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

  DateTime _parseKey(String key) {
    final p = key.split('-');
    return DateTime(int.parse(p[0]), int.parse(p[1]), int.parse(p[2]));
  }

  List<QuestTitleEntry> get _questChoices =>
      flattenQuestTitles(questTree).where((q) => q.id != 'root').toList();

  DayLog _logFor(String key) =>
      _logs[key] ?? const DayLog(completedQuestIds: [], note: '');

  bool _hasActivity(String key) {
    final e = _logs[key];
    if (e == null) return false;
    return e.note.trim().isNotEmpty || e.completedQuestIds.isNotEmpty;
  }

  void _toggleQuest(String questId) {
    setState(() {
      final cur = _logFor(_selectedKey);
      final set = {...cur.completedQuestIds};
      if (set.contains(questId)) {
        set.remove(questId);
      } else {
        set.add(questId);
      }
      _logs[_selectedKey] = cur.copyWith(completedQuestIds: set.toList());
    });
  }

  void _setNote(String note) {
    setState(() {
      final cur = _logFor(_selectedKey);
      _logs[_selectedKey] = cur.copyWith(note: note);
    });
  }

  List<({DateTime date, bool inMonth})> _calendarCells(int year, int month) {
    final first = DateTime(year, month, 1);
    final firstCol = first.weekday % 7;
    final dim = DateTime(year, month + 1, 0).day;
    final cells = <({DateTime date, bool inMonth})>[];

    for (int i = 0; i < firstCol; i++) {
      final day = i - firstCol + 1;
      cells.add((date: DateTime(year, month, day), inMonth: false));
    }
    for (int d = 1; d <= dim; d++) {
      cells.add((date: DateTime(year, month, d), inMonth: true));
    }
    var next = DateTime(year, month, dim + 1);
    while (cells.length % 7 != 0 || cells.length < 42) {
      cells.add((date: next, inMonth: false));
      next = next.add(const Duration(days: 1));
    }
    return cells;
  }

  bool _isToday(DateTime d) => _toKey(d) == _toKey(_today);

  String _weekdayKo(DateTime d) => _weekLabels[d.weekday % 7];

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final viewMonth = DateTime(_today.year, _today.month + _monthOffset, 1);
    final y = viewMonth.year;
    final m = viewMonth.month;
    final cells = _calendarCells(y, m);
    final selectedLog = _logFor(_selectedKey);
    final selectedDate = _parseKey(_selectedKey);

    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 0, 16, 24),
      children: [
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: AppColors.slate800,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: AppColors.slate700),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withValues(alpha: 0.12),
                blurRadius: 8,
              ),
            ],
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Icon(Icons.calendar_month_rounded,
                      size: 18, color: AppColors.indigo600),
                  const SizedBox(width: 8),
                  Text(
                    '성장 아카이브',
                    style: Theme.of(context).textTheme.titleSmall?.copyWith(
                          fontWeight: FontWeight.w800,
                          color: scheme.onSurface,
                        ),
                  ),
                  const Spacer(),
                  IconButton(
                    onPressed: () => setState(() => _monthOffset--),
                    icon: const Icon(Icons.chevron_left),
                    color: scheme.onSurfaceVariant,
                    style: IconButton.styleFrom(
                      side: BorderSide(color: AppColors.slate700),
                    ),
                  ),
                  SizedBox(
                    width: 120,
                    child: Text(
                      '$y년 $m월',
                      textAlign: TextAlign.center,
                      style: Theme.of(context).textTheme.labelLarge?.copyWith(
                            fontWeight: FontWeight.w800,
                          ),
                    ),
                  ),
                  IconButton(
                    onPressed: () => setState(() => _monthOffset++),
                    icon: const Icon(Icons.chevron_right),
                    color: scheme.onSurfaceVariant,
                    style: IconButton.styleFrom(
                      side: BorderSide(color: AppColors.slate700),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Text(
                '완료·기록이 있는 날은 민트/인디고 점으로 표시합니다. (포트폴리오 빌더 연계 예정)',
                style: Theme.of(context).textTheme.labelSmall?.copyWith(
                      color: scheme.onSurfaceVariant,
                      height: 1.35,
                    ),
              ),
              const SizedBox(height: 12),
              Row(
                children: _weekLabels
                    .map(
                      (w) => Expanded(
                        child: Text(
                          w,
                          textAlign: TextAlign.center,
                          style: Theme.of(context).textTheme.labelSmall?.copyWith(
                                fontWeight: FontWeight.w700,
                                color: scheme.onSurfaceVariant,
                              ),
                        ),
                      ),
                    )
                    .toList(),
              ),
              const SizedBox(height: 6),
              GridView.builder(
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                  crossAxisCount: 7,
                  mainAxisExtent: 44,
                  crossAxisSpacing: 4,
                  mainAxisSpacing: 4,
                ),
                itemCount: cells.length,
                itemBuilder: (context, i) {
                  final c = cells[i];
                  final key = _toKey(c.date);
                  final active = key == _selectedKey;
                  final dot = c.inMonth && _hasActivity(key);
                  final today = c.inMonth && _isToday(c.date);

                  Color bg = AppColors.slate900.withValues(alpha: 0.45);
                  Color fg = scheme.onSurface;
                  Color border = AppColors.slate700;
                  if (!c.inMonth) {
                    fg = scheme.onSurfaceVariant.withValues(alpha: 0.35);
                  } else if (active) {
                    bg = AppColors.indigo600.withValues(alpha: 0.18);
                    border = AppColors.indigo600.withValues(alpha: 0.45);
                  } else if (today) {
                    bg = const Color(0xFF34D399).withValues(alpha: 0.12);
                    border = const Color(0xFF34D399).withValues(alpha: 0.35);
                  }

                  return Material(
                    color: Colors.transparent,
                    child: InkWell(
                      onTap: () => _selectDay(key),
                      borderRadius: BorderRadius.circular(10),
                      child: Container(
                        decoration: BoxDecoration(
                          color: c.inMonth ? bg : Colors.transparent,
                          borderRadius: BorderRadius.circular(10),
                          border: Border.all(color: border),
                        ),
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Text(
                              '${c.date.day}',
                              style: Theme.of(context).textTheme.labelMedium?.copyWith(
                                    fontWeight: FontWeight.w800,
                                    color: fg,
                                  ),
                            ),
                            const SizedBox(height: 2),
                            if (dot)
                              Container(
                                width: 5,
                                height: 5,
                                decoration: BoxDecoration(
                                  shape: BoxShape.circle,
                                  color: active
                                      ? AppColors.indigo600
                                      : const Color(0xFF34D399),
                                ),
                              )
                            else
                              const SizedBox(height: 5),
                          ],
                        ),
                      ),
                    ),
                  );
                },
              ),
            ],
          ),
        ),
        const SizedBox(height: 16),
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: AppColors.slate900,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: AppColors.slate700),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Daily Log',
                style: Theme.of(context).textTheme.labelSmall?.copyWith(
                      fontWeight: FontWeight.w700,
                      color: scheme.onSurfaceVariant,
                    ),
              ),
              const SizedBox(height: 6),
              Text(
                '${selectedDate.year}년 ${selectedDate.month}월 ${selectedDate.day}일 (${_weekdayKo(selectedDate)})',
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.w800,
                    ),
              ),
              const SizedBox(height: 16),
              Text(
                '이날 달성한 퀘스트',
                style: Theme.of(context).textTheme.labelSmall?.copyWith(
                      fontWeight: FontWeight.w700,
                      color: scheme.onSurfaceVariant,
                    ),
              ),
              const SizedBox(height: 8),
              Container(
                constraints: const BoxConstraints(maxHeight: 180),
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: AppColors.slate800,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: AppColors.slate700),
                ),
                child: ListView(
                  shrinkWrap: true,
                  children: _questChoices
                      .map(
                        (q) => CheckboxListTile(
                          dense: true,
                          contentPadding: EdgeInsets.zero,
                          value: selectedLog.completedQuestIds.contains(q.id),
                          onChanged: (_) => _toggleQuest(q.id),
                          activeColor: AppColors.indigo600,
                          title: Text(
                            q.title,
                            style: Theme.of(context).textTheme.labelMedium,
                          ),
                        ),
                      )
                      .toList(),
                ),
              ),
              const SizedBox(height: 16),
              Text(
                '배운 것 · 해결한 것 (마크다운 스타일 자유 기록)',
                style: Theme.of(context).textTheme.labelSmall?.copyWith(
                      fontWeight: FontWeight.w700,
                      color: scheme.onSurfaceVariant,
                    ),
              ),
              const SizedBox(height: 8),
              TextField(
                controller: _noteController,
                onChanged: _setNote,
                minLines: 5,
                maxLines: 10,
                style: Theme.of(context).textTheme.bodyMedium,
                decoration: InputDecoration(
                  hintText:
                      '예: 오늘은 스키마에서 scope3 경계를 어떻게 끊을지 고민했다…',
                  filled: true,
                  fillColor: AppColors.slate800,
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide: BorderSide(color: AppColors.slate700),
                  ),
                  enabledBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide: BorderSide(color: AppColors.slate700),
                  ),
                  focusedBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide: BorderSide(color: AppColors.indigo600.withValues(alpha: 0.65)),
                  ),
                ),
              ),
              const SizedBox(height: 16),
              SizedBox(
                width: double.infinity,
                child: FilledButton.icon(
                  onPressed: () {
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(content: Text('저장됨 (로컬 목업)')),
                    );
                  },
                  icon: const Icon(Icons.save_outlined, size: 18),
                  label: const Text('저장 (로컬)'),
                  style: FilledButton.styleFrom(
                    backgroundColor: AppColors.indigo600,
                    padding: const EdgeInsets.symmetric(vertical: 14),
                  ),
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}
