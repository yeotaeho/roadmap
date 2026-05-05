import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../data/dashboard_mock_data.dart';

class SectorDetailPage extends StatelessWidget {
  const SectorDetailPage({required this.slug, super.key});

  final String slug;

  @override
  Widget build(BuildContext context) {
    final sector = DashboardMockData.sectorBySlug(slug);
    final detail = DashboardMockData.pulseDetail(slug);

    if (sector == null || detail == null) {
      return Scaffold(
        appBar: AppBar(title: const Text('섹터')),
        body: const Center(child: Text('데이터를 찾을 수 없습니다.')),
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: Text(sector.title, maxLines: 1, overflow: TextOverflow.ellipsis),
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text(
            detail.headline,
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.w700,
                  height: 1.35,
                ),
          ),
          const SizedBox(height: 16),
          Text(
            '왜 중요한가',
            style: Theme.of(context).textTheme.titleSmall?.copyWith(
                  fontWeight: FontWeight.w600,
                ),
          ),
          const SizedBox(height: 8),
          ...detail.whyItMatters.map(
            (t) => Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('· '),
                  Expanded(child: Text(t, style: const TextStyle(height: 1.4))),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),
          Text(
            '신호',
            style: Theme.of(context).textTheme.titleSmall?.copyWith(
                  fontWeight: FontWeight.w600,
                ),
          ),
          const SizedBox(height: 8),
          ...detail.signals.map(
            (s) => ListTile(
              contentPadding: EdgeInsets.zero,
              title: Text(s.label),
              subtitle: Text(s.value),
            ),
          ),
          const SizedBox(height: 16),
          Text(
            '리스크',
            style: Theme.of(context).textTheme.titleSmall?.copyWith(
                  fontWeight: FontWeight.w600,
                ),
          ),
          const SizedBox(height: 8),
          ...detail.risks.map(
            (t) => Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Text('• $t', style: const TextStyle(height: 1.4)),
            ),
          ),
          const SizedBox(height: 24),
          FilledButton.icon(
            onPressed: () => context.go('/coach'),
            icon: const Icon(Icons.auto_awesome_outlined),
            label: const Text('AI 코치에게 물어보기'),
          ),
          const SizedBox(height: 8),
          OutlinedButton.icon(
            onPressed: () => context.go('/roadmap'),
            icon: const Icon(Icons.map_outlined),
            label: const Text('로드맵으로 보내기'),
          ),
        ],
      ),
    );
  }
}
