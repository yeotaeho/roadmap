import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/theme/app_colors.dart';
import '../../data/dashboard_mock_data.dart';

/// 블루오션 — 세로 스크롤 카드 + 상단 고정 분야 칩(펄스 Top 6 섹터와 동일).
class GapTab extends StatefulWidget {
  const GapTab({super.key});

  @override
  State<GapTab> createState() => _GapTabState();
}

class _GapTabState extends State<GapTab> {
  /// `null`이면 전체 표시.
  String? _sectorFilter;

  @override
  Widget build(BuildContext context) {
    final items = DashboardMockData.gapIssuesForSector(_sectorFilter);

    return CustomScrollView(
      slivers: [
        SliverToBoxAdapter(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
            child: Text(
              '세상의 결핍을 기회로 — 분야를 골라보거나 아래로 스크롤하세요.',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(height: 1.35),
            ),
          ),
        ),
        const SliverToBoxAdapter(child: SizedBox(height: 12)),
        SliverPersistentHeader(
          pinned: true,
          delegate: _GapSectorHeaderDelegate(
            selectedFilter: _sectorFilter,
            onFilterChanged: (id) => setState(() => _sectorFilter = id),
          ),
        ),
        if (items.isEmpty)
          SliverFillRemaining(
            hasScrollBody: false,
            child: Center(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Text(
                  '이 분야에 등록된 카드가 없습니다.',
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        color: Theme.of(context).colorScheme.onSurfaceVariant,
                      ),
                ),
              ),
            ),
          )
        else
          SliverPadding(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
            sliver: SliverList.separated(
              itemCount: items.length,
              separatorBuilder: (context, index) => const SizedBox(height: 12),
              itemBuilder: (context, index) {
                final card = items[index];
                return _GapVerticalCard(
                  card: card,
                  onDeepDive: () => context.push('/gap/issues/${card.id}'),
                );
              },
            ),
          ),
      ],
    );
  }
}

const double _kSectorBarHeight = 56;

class _GapSectorHeaderDelegate extends SliverPersistentHeaderDelegate {
  _GapSectorHeaderDelegate({
    required this.selectedFilter,
    required this.onFilterChanged,
  });

  final String? selectedFilter;
  final ValueChanged<String?> onFilterChanged;

  @override
  double get minExtent => _kSectorBarHeight;

  @override
  double get maxExtent => _kSectorBarHeight;

  @override
  Widget build(
    BuildContext context,
    double shrinkOffset,
    bool overlapsContent,
  ) {
    final scheme = Theme.of(context).colorScheme;
    return Material(
      color: scheme.surface,
      elevation: overlapsContent ? 1.2 : 0,
      shadowColor: Colors.black.withValues(alpha: 0.25),
      child: SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        child: Row(
          children: [
            ChoiceChip(
              label: const Text('전체'),
              selected: selectedFilter == null,
              onSelected: (v) {
                if (v) onFilterChanged(null);
              },
              selectedColor: AppColors.indigo600.withValues(alpha: 0.35),
              checkmarkColor: AppColors.indigo600,
              labelStyle: TextStyle(
                color: selectedFilter == null
                    ? AppColors.indigo600
                    : scheme.onSurface,
                fontWeight:
                    selectedFilter == null ? FontWeight.w600 : FontWeight.w500,
                fontSize: 12,
              ),
            ),
            const SizedBox(width: 8),
            ...DashboardMockData.pulseSectors.map((s) {
              final short = DashboardMockData.gapSectorChipLabels[s.slug] ??
                  s.title;
              final selected = selectedFilter == s.slug;
              return Padding(
                padding: const EdgeInsets.only(right: 8),
                child: ChoiceChip(
                  label: Text(
                    short,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(fontSize: 12),
                  ),
                  selected: selected,
                  onSelected: (v) {
                    if (v) onFilterChanged(s.slug);
                  },
                  selectedColor: AppColors.indigo600.withValues(alpha: 0.35),
                  checkmarkColor: AppColors.indigo600,
                  labelStyle: TextStyle(
                    color: selected
                        ? AppColors.indigo600
                        : scheme.onSurface,
                    fontWeight: selected ? FontWeight.w600 : FontWeight.w500,
                    fontSize: 12,
                  ),
                ),
              );
            }),
          ],
        ),
      ),
    );
  }

  @override
  bool shouldRebuild(covariant _GapSectorHeaderDelegate oldDelegate) {
    return selectedFilter != oldDelegate.selectedFilter;
  }
}

class _GapVerticalCard extends StatelessWidget {
  const _GapVerticalCard({
    required this.card,
    required this.onDeepDive,
  });

  final GapIssueCard card;
  final VoidCallback onDeepDive;

  static double _scoreNorm(int score) => (score.clamp(0, 100)) / 100.0;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final sector = DashboardMockData.sectorBySlug(card.sectorId);
    final accent = sector?.accent ?? AppColors.sectorMetricAccent;
    final titleStyle = Theme.of(context).textTheme.titleSmall?.copyWith(
          fontWeight: FontWeight.w800,
        );

    return Material(
      color: scheme.surfaceContainerLow.withValues(alpha: 0.9),
      borderRadius: BorderRadius.circular(16),
      clipBehavior: Clip.antiAlias,
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  child: Text(
                    sector?.title ?? card.sectorId,
                    maxLines: 3,
                    overflow: TextOverflow.ellipsis,
                    style: titleStyle,
                  ),
                ),
                const SizedBox(width: 6),
                if (sector != null) ...[
                  Text(
                    '${sector.score}',
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.w900,
                          color: accent,
                        ),
                  ),
                ],
              ],
            ),
            const SizedBox(height: 6),
            if (sector != null)
              Row(
                children: [
                  Flexible(
                    child: Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 8,
                        vertical: 3,
                      ),
                      decoration: BoxDecoration(
                        color: accent.withValues(alpha: 0.2),
                        borderRadius: BorderRadius.circular(6),
                        border: Border.all(
                          color: accent.withValues(alpha: 0.45),
                        ),
                      ),
                      child: Text(
                        sector.status,
                        style: TextStyle(
                          color: accent,
                          fontWeight: FontWeight.w700,
                          fontSize: 12,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                  ),
                  const Spacer(),
                  Text.rich(
                    TextSpan(
                      style: TextStyle(
                        color: scheme.onSurfaceVariant,
                        fontSize: 12,
                      ),
                      children: [
                        const TextSpan(text: '모멘텀 '),
                        TextSpan(
                          text:
                              '${(_scoreNorm(sector.score) * 100).round()}%',
                          style: TextStyle(
                            color: accent,
                            fontWeight: FontWeight.w700,
                            fontSize: 12,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            if (sector != null) const SizedBox(height: 10),
            if (sector != null)
              ClipRRect(
                borderRadius: BorderRadius.circular(4),
                child: LinearProgressIndicator(
                  value: _scoreNorm(sector.score),
                  minHeight: 6,
                  backgroundColor: AppColors.gaugeTrackForAccent(accent),
                  color: accent,
                ),
              ),
            if (sector != null) const SizedBox(height: 14),
            Text(
              '결핍',
              style: Theme.of(context).textTheme.labelMedium?.copyWith(
                    color: scheme.onSurfaceVariant,
                    fontWeight: FontWeight.w600,
                  ),
            ),
            const SizedBox(height: 6),
            Text(
              card.problem,
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    height: 1.4,
                    color: scheme.onSurface,
                  ),
            ),
            const SizedBox(height: 12),
            Divider(
              height: 1,
              color: scheme.outlineVariant.withValues(alpha: 0.45),
            ),
            const SizedBox(height: 10),
            Text(
              '기회',
              style: Theme.of(context).textTheme.labelMedium?.copyWith(
                    color: accent,
                    fontWeight: FontWeight.w700,
                  ),
            ),
            const SizedBox(height: 6),
            Text(
              card.chance,
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    height: 1.4,
                    color: scheme.onSurface,
                  ),
            ),
            const SizedBox(height: 14),
            FilledButton(
              onPressed: onDeepDive,
              style: FilledButton.styleFrom(
                backgroundColor: accent,
                foregroundColor: _onAccentForeground(accent),
              ),
              child: const Text('이 분야 파고들기'),
            ),
          ],
        ),
      ),
    );
  }

  /// 진한/연한 액센트 모두에서 버튼 글자 대비 확보.
  static Color _onAccentForeground(Color accent) {
    final luminance = accent.computeLuminance();
    return luminance > 0.55 ? const Color(0xFF0F172A) : Colors.white;
  }
}
