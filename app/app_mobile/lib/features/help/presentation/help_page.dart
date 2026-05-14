import 'package:flutter/material.dart';

/// 도움말 화면 — FAQ + 문의 안내 (정적).
class HelpPage extends StatelessWidget {
  const HelpPage({super.key});

  static const List<_FaqItem> _faqs = <_FaqItem>[
    _FaqItem(
      category: '계정',
      question: '로그인 방법은 어떤 것이 있나요?',
      answer: '구글, 카카오, 네이버 로그인을 지원합니다.\n'
          '한 번 로그인하면 디바이스에 안전하게 토큰이 저장되어 자동 로그인됩니다.',
    ),
    _FaqItem(
      category: '계정',
      question: '닉네임이나 관심 분야를 변경하고 싶어요.',
      answer: '메뉴 > 프로필 화면에서 닉네임, 목표 직무, 관심 분야를 모두 수정할 수 있습니다.\n'
          '저장 버튼을 누르면 즉시 반영됩니다.',
    ),
    _FaqItem(
      category: '인사이트',
      question: '대시보드의 4가지 탭은 무엇인가요?',
      answer: '펄스: 산업별 트렌드 속도\n'
          '블루오션: 시장의 빈 자리(갭) 분석\n'
          '싱크: 트렌드/이슈/정책 정렬\n'
          '찬스: 실행 가능한 기회 카드',
    ),
    _FaqItem(
      category: '인사이트',
      question: '데이터는 얼마나 자주 업데이트되나요?',
      answer: '핵심 지표는 매일 1회, 일부 보조 지표는 주 1회 새로고침됩니다.\n'
          '리포트 카드의 우측 상단 시간 표기를 참고해 주세요.',
    ),
    _FaqItem(
      category: '알림',
      question: '주간 리포트 알림은 어떻게 끄나요?',
      answer: '설정 > 알림 > "주간 인사이트 리포트" 토글에서 끌 수 있습니다.',
    ),
    _FaqItem(
      category: '문제 해결',
      question: '로그인 후 빈 화면이 보여요.',
      answer: '대부분 일시적인 네트워크 이슈입니다.\n'
          '앱을 재실행하거나 Wi-Fi/셀룰러 연결을 확인해 주세요.\n'
          '계속 문제가 발생하면 도움말 > 문의하기로 알려주세요.',
    ),
    _FaqItem(
      category: '문제 해결',
      question: '네이버 로그인 시 빈 화면이 나타나요.',
      answer: 'Chrome Custom Tabs 와 일부 단말의 호환 이슈로 알려진 현상입니다.\n'
          '네이버 앱을 설치한 후 다시 시도하면 정상 동작합니다.',
    ),
  ];

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final cs = theme.colorScheme;

    final byCategory = <String, List<_FaqItem>>{};
    for (final f in _faqs) {
      byCategory.putIfAbsent(f.category, () => <_FaqItem>[]).add(f);
    }

    return Scaffold(
      appBar: AppBar(title: const Text('도움말')),
      body: ListView(
        children: [
          Container(
            margin: const EdgeInsets.fromLTRB(16, 16, 16, 8),
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: cs.primary.withValues(alpha: 0.10),
              borderRadius: BorderRadius.circular(14),
            ),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(Icons.support_agent, color: cs.primary),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        '무엇이든 물어보세요',
                        style: theme.textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        '아래 자주 묻는 질문에서 답을 찾지 못하셨다면\n'
                        '아래 "문의하기" 버튼으로 연락 주세요. (영업일 기준 1-2일 내 회신)',
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: cs.onSurfaceVariant,
                          height: 1.5,
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
          for (final entry in byCategory.entries) ...[
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 16, 20, 6),
              child: Text(
                entry.key,
                style: TextStyle(
                  color: cs.primary,
                  fontWeight: FontWeight.w800,
                  letterSpacing: 0.5,
                  fontSize: 12,
                ),
              ),
            ),
            ...entry.value.map((f) => _FaqTile(item: f)),
            const Divider(height: 1),
          ],
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 24, 20, 24),
            child: Column(
              children: [
                SizedBox(
                  width: double.infinity,
                  height: 52,
                  child: FilledButton.icon(
                    onPressed: () => _showContact(context),
                    icon: const Icon(Icons.email_outlined),
                    label: const Text('문의하기'),
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  '문의 메일 · support@yeotaeho.kr',
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: cs.onSurfaceVariant,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  void _showContact(BuildContext context) {
    showModalBottomSheet<void>(
      context: context,
      builder: (ctx) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 16, 20, 20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                '문의하기',
                style: Theme.of(ctx).textTheme.titleLarge?.copyWith(
                      fontWeight: FontWeight.w800,
                    ),
              ),
              const SizedBox(height: 12),
              const Text(
                '문의 메일 주소: support@yeotaeho.kr\n'
                '메일 본문에 다음 내용을 포함해 주시면 빠른 응대가 가능합니다.\n\n'
                '· 이용 환경 (Android/iOS 버전, 단말명)\n'
                '· 문제 발생 시각과 재현 단계\n'
                '· 사용 중인 계정 이메일',
                style: TextStyle(height: 1.6),
              ),
              const SizedBox(height: 16),
              SizedBox(
                width: double.infinity,
                child: FilledButton(
                  onPressed: () => Navigator.of(ctx).pop(),
                  child: const Text('확인'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _FaqTile extends StatelessWidget {
  const _FaqTile({required this.item});
  final _FaqItem item;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return ExpansionTile(
      tilePadding: const EdgeInsets.symmetric(horizontal: 20, vertical: 4),
      childrenPadding: const EdgeInsets.fromLTRB(20, 0, 20, 18),
      leading: const Icon(Icons.help_outline, size: 20),
      title: Text(
        item.question,
        style: const TextStyle(fontWeight: FontWeight.w600),
      ),
      children: [
        Align(
          alignment: Alignment.centerLeft,
          child: Text(
            item.answer,
            style: theme.textTheme.bodyMedium?.copyWith(height: 1.55),
          ),
        ),
      ],
    );
  }
}

class _FaqItem {
  const _FaqItem({
    required this.category,
    required this.question,
    required this.answer,
  });

  final String category;
  final String question;
  final String answer;
}
