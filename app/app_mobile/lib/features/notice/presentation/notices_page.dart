import 'package:flutter/material.dart';

/// 공지사항 화면 (정적 데이터).
///
/// 추후 백엔드 API (`GET /api/notices`) 가 추가되면
/// `_seed` 를 비동기 로더로 교체하면 됩니다.
class NoticesPage extends StatelessWidget {
  const NoticesPage({super.key});

  static final List<_Notice> _seed = <_Notice>[
    _Notice(
      title: '청년 인사이트 v1.0 정식 출시',
      date: DateTime(2026, 5, 1),
      tag: '업데이트',
      body:
          '안녕하세요, 청년 인사이트 팀입니다.\n\n'
          '오늘부터 모바일 앱 v1.0 이 정식 출시됩니다.\n'
          '인사이트 대시보드, 상담, 로드맵, AI 코치 4가지 기능을 한 곳에서 사용해 보세요.\n\n'
          '여러분의 의견을 기다립니다. 도움말 > 문의하기로 언제든 알려주세요.',
    ),
    _Notice(
      title: '소셜 로그인 안정화',
      date: DateTime(2026, 4, 22),
      tag: '안정화',
      body:
          '구글·카카오·네이버 로그인 흐름을 안정화했습니다.\n'
          '- 토큰 만료 시 자동 갱신 강화\n'
          '- 일부 단말의 콜백 누락 이슈 수정',
    ),
    _Notice(
      title: '주간 인사이트 리포트 알림',
      date: DateTime(2026, 4, 15),
      tag: '기능',
      body:
          '매주 월요일 오전 8시, 한 주의 핵심 트렌드를 정리한\n'
          '주간 인사이트 리포트 알림이 발송됩니다.\n'
          '설정 > 알림 에서 켜고 끌 수 있습니다.',
    ),
    _Notice(
      title: '서비스 점검 안내',
      date: DateTime(2026, 4, 6),
      tag: '점검',
      body:
          '4월 7일(일) 02:00 ~ 04:00 (KST) 동안 서비스 점검이 진행됩니다.\n'
          '해당 시간에는 일부 기능 이용이 제한될 수 있습니다.',
    ),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('공지사항')),
      body: ListView.separated(
        padding: const EdgeInsets.symmetric(vertical: 8),
        itemCount: _seed.length,
        separatorBuilder: (context, index) => const Divider(height: 1),
        itemBuilder: (context, i) => _NoticeTile(notice: _seed[i]),
      ),
    );
  }
}

class _NoticeTile extends StatelessWidget {
  const _NoticeTile({required this.notice});
  final _Notice notice;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final cs = theme.colorScheme;

    return ExpansionTile(
      tilePadding: const EdgeInsets.symmetric(horizontal: 20, vertical: 4),
      childrenPadding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
      title: Row(
        children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
            decoration: BoxDecoration(
              color: cs.primary.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(999),
            ),
            child: Text(
              notice.tag,
              style: theme.textTheme.labelSmall?.copyWith(
                color: cs.primary,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              notice.title,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(fontWeight: FontWeight.w600),
            ),
          ),
        ],
      ),
      subtitle: Padding(
        padding: const EdgeInsets.only(top: 4),
        child: Text(
          _formatDate(notice.date),
          style: theme.textTheme.bodySmall?.copyWith(color: cs.onSurfaceVariant),
        ),
      ),
      children: [
        Align(
          alignment: Alignment.centerLeft,
          child: Text(
            notice.body,
            style: theme.textTheme.bodyMedium?.copyWith(height: 1.55),
          ),
        ),
      ],
    );
  }

  String _formatDate(DateTime d) {
    final mm = d.month.toString().padLeft(2, '0');
    final dd = d.day.toString().padLeft(2, '0');
    return '${d.year}.$mm.$dd';
  }
}

class _Notice {
  _Notice({
    required this.title,
    required this.date,
    required this.tag,
    required this.body,
  });

  final String title;
  final DateTime date;
  final String tag;
  final String body;
}
