import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../data/dashboard_mock_data.dart';

class ChanceDetailPage extends StatelessWidget {
  const ChanceDetailPage({required this.opportunityId, super.key});

  final String opportunityId;

  @override
  Widget build(BuildContext context) {
    final d = DashboardMockData.chanceDetail(opportunityId);
    if (d == null) {
      return Scaffold(
        appBar: AppBar(title: const Text('찬스')),
        body: const Center(child: Text('기회를 찾을 수 없습니다.')),
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: Text(d.title, maxLines: 1, overflow: TextOverflow.ellipsis),
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Row(
            children: [
              Chip(label: Text(d.type)),
              const SizedBox(width: 8),
              Text(
                d.dday,
                style: Theme.of(context).textTheme.labelLarge?.copyWith(
                      fontWeight: FontWeight.w700,
                      color: Theme.of(context).colorScheme.error,
                    ),
              ),
              const Spacer(),
              Text(
                '매칭 ${d.match}점',
                style: Theme.of(context).textTheme.titleSmall?.copyWith(
                      color: Theme.of(context).colorScheme.primary,
                      fontWeight: FontWeight.w700,
                    ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Text(
            d.summary,
            style: Theme.of(context).textTheme.bodyLarge?.copyWith(height: 1.45),
          ),
          const SizedBox(height: 20),
          Text(
            '지원 자격(체크)',
            style: Theme.of(context).textTheme.titleSmall?.copyWith(
                  fontWeight: FontWeight.w600,
                ),
          ),
          const SizedBox(height: 8),
          ...d.eligibility.map(
            (t) => Padding(
              padding: const EdgeInsets.only(bottom: 6),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('· '),
                  Expanded(child: Text(t)),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),
          Text(
            '준비물',
            style: Theme.of(context).textTheme.titleSmall?.copyWith(
                  fontWeight: FontWeight.w600,
                ),
          ),
          const SizedBox(height: 8),
          ...d.prepare.map(
            (t) => Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(Icons.edit_note, size: 20, color: Theme.of(context).colorScheme.primary),
                  const SizedBox(width: 8),
                  Expanded(child: Text(t, style: const TextStyle(height: 1.4))),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),
          FilledButton.icon(
            onPressed: () => context.go('/coach'),
            icon: const Icon(Icons.auto_awesome_outlined),
            label: const Text('AI 코치에게 준비 코칭 받기'),
          ),
          const SizedBox(height: 8),
          OutlinedButton(
            onPressed: () {
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(
                  content: Text('공식 URL은 백엔드/API 연동 후 열리도록 연결됩니다.'),
                ),
              );
            },
            child: const Text('공식 공고 열기(예시)'),
          ),
        ],
      ),
    );
  }
}
