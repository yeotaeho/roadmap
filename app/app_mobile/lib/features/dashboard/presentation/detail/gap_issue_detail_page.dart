import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../data/dashboard_mock_data.dart';

class GapIssueDetailPage extends StatelessWidget {
  const GapIssueDetailPage({required this.issueId, super.key});

  final String issueId;

  @override
  Widget build(BuildContext context) {
    final d = DashboardMockData.gapDetail(issueId);
    if (d == null) {
      return Scaffold(
        appBar: AppBar(title: const Text('블루오션')),
        body: const Center(child: Text('이슈를 찾을 수 없습니다.')),
      );
    }

    return Scaffold(
      appBar: AppBar(title: const Text('이슈 상세')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _SectionCard(
            title: '문제',
            child: Text(d.problem, style: const TextStyle(height: 1.4)),
          ),
          const SizedBox(height: 12),
          _SectionCard(
            title: '기회',
            child: Text(d.chance, style: const TextStyle(height: 1.4)),
          ),
          const SizedBox(height: 12),
          Text(
            d.summary,
            style: Theme.of(context).textTheme.bodyLarge?.copyWith(height: 1.45),
          ),
          const SizedBox(height: 20),
          Text(
            '이해관계자(예시)',
            style: Theme.of(context).textTheme.titleSmall?.copyWith(
                  fontWeight: FontWeight.w600,
                ),
          ),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: d.stakeholders
                .map((s) => Chip(label: Text(s), visualDensity: VisualDensity.compact))
                .toList(),
          ),
          const SizedBox(height: 20),
          Text(
            '다음 행동',
            style: Theme.of(context).textTheme.titleSmall?.copyWith(
                  fontWeight: FontWeight.w600,
                ),
          ),
          const SizedBox(height: 8),
          ...d.nextSteps.map(
            (t) => Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(Icons.check_circle_outline, size: 18, color: Theme.of(context).colorScheme.primary),
                  const SizedBox(width: 8),
                  Expanded(child: Text(t, style: const TextStyle(height: 1.4))),
                ],
              ),
            ),
          ),
          const SizedBox(height: 24),
          FilledButton.icon(
            onPressed: () => context.go('/coach'),
            icon: const Icon(Icons.chat_bubble_outline),
            label: const Text('AI 코치에게 질문하기'),
          ),
        ],
      ),
    );
  }
}

class _SectionCard extends StatelessWidget {
  const _SectionCard({required this.title, required this.child});

  final String title;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: scheme.surfaceContainerHighest.withValues(alpha: 0.5),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: Theme.of(context).textTheme.labelLarge?.copyWith(
                  color: scheme.primary,
                  fontWeight: FontWeight.w600,
                ),
          ),
          const SizedBox(height: 8),
          child,
        ],
      ),
    );
  }
}
