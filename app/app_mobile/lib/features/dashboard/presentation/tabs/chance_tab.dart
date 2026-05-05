import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../../core/theme/app_colors.dart';
import '../../data/dashboard_mock_data.dart';

class ChanceTab extends StatelessWidget {
  const ChanceTab({super.key});

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
      children: [
        Text(
          '매칭된 기회를 아래로 스크롤하며 확인하고, 바로 행동으로 연결하세요.',
          style: Theme.of(context).textTheme.bodyMedium?.copyWith(height: 1.35),
        ),
        const SizedBox(height: 16),
        ...DashboardMockData.chanceCards.map(
          (o) => Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: _ChanceCard(
              card: o,
              onDetail: () => context.push('/chance/opportunities/${o.id}'),
            ),
          ),
        ),
      ],
    );
  }
}

class _ChanceCard extends StatelessWidget {
  const _ChanceCard({
    required this.card,
    required this.onDetail,
  });

  final ChanceCard card;
  final VoidCallback onDetail;

  static const Color _mutedOnCard = Color(0xFF94A3B8);

  double get _matchNorm => (card.match.clamp(0, 100)) / 100.0;

  @override
  Widget build(BuildContext context) {
    final accent = AppColors.sectorMetricAccent;
    return Card(
      elevation: 0,
      color: AppColors.syncChanceCardSurface,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          mainAxisSize: MainAxisSize.min,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Flexible(
                  child: Container(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                    decoration: BoxDecoration(
                      color: accent.withValues(alpha: 0.2),
                      borderRadius: BorderRadius.circular(6),
                      border: Border.all(
                        color: accent.withValues(alpha: 0.45),
                      ),
                    ),
                    child: Text(
                      card.type,
                      style: Theme.of(context).textTheme.labelMedium?.copyWith(
                            fontWeight: FontWeight.w700,
                            color: accent,
                          ),
                    ),
                  ),
                ),
                const Spacer(),
                Text(
                  card.dday,
                  style: Theme.of(context).textTheme.labelLarge?.copyWith(
                        fontWeight: FontWeight.w700,
                        color: _mutedOnCard,
                      ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Text(
              card.title,
              style: Theme.of(context).textTheme.titleSmall?.copyWith(
                    fontWeight: FontWeight.w800,
                    color: Colors.white,
                  ),
              maxLines: 3,
              overflow: TextOverflow.ellipsis,
            ),
            const SizedBox(height: 10),
            Align(
              alignment: Alignment.centerRight,
              child: Text.rich(
                TextSpan(
                  style: Theme.of(context).textTheme.labelLarge?.copyWith(
                        color: _mutedOnCard,
                      ),
                  children: [
                    const TextSpan(text: '모멘텀 '),
                    TextSpan(
                      text: '${card.match}%',
                      style: TextStyle(
                        color: accent,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 8),
            ClipRRect(
              borderRadius: BorderRadius.circular(4),
              child: LinearProgressIndicator(
                value: _matchNorm,
                minHeight: 6,
                backgroundColor: AppColors.gaugeTrackForAccent(accent),
                color: accent,
              ),
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Icon(Icons.bolt, size: 18, color: accent),
                const SizedBox(width: 6),
                Text(
                  '매칭 ${card.match}점',
                  style: Theme.of(context).textTheme.labelLarge?.copyWith(
                        color: accent,
                        fontWeight: FontWeight.w700,
                      ),
                ),
              ],
            ),
            const SizedBox(height: 14),
            FilledButton(
              onPressed: onDetail,
              style: FilledButton.styleFrom(
                backgroundColor: accent,
                foregroundColor: Colors.white,
              ),
              child: const Text('자세히 보기'),
            ),
          ],
        ),
      ),
    );
  }
}
