import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/providers/core_providers.dart';

/// OAuth 로그인 후 `user_sync_profiles` 가 비어 있는 신규 사용자에게
/// 목표 직무 + 관심 키워드를 한 번 받아 백엔드(`PUT /api/user/sync-profile`)에 저장한다.
/// 웹의 `/signup` 페이지와 동일한 옵션 세트를 사용한다.
class SignupCompletePage extends ConsumerStatefulWidget {
  const SignupCompletePage({super.key});

  @override
  ConsumerState<SignupCompletePage> createState() => _SignupCompletePageState();
}

class _SignupCompletePageState extends ConsumerState<SignupCompletePage> {
  static const List<_InterestOption> _interestOptions = <_InterestOption>[
    _InterestOption(value: 'economy', label: '경제'),
    _InterestOption(value: 'politics', label: '정치'),
    _InterestOption(value: 'society', label: '사회'),
    _InterestOption(value: 'culture', label: '문화'),
    _InterestOption(value: 'world', label: '세계'),
    _InterestOption(value: 'it-science', label: 'IT/과학'),
    _InterestOption(value: 'sports', label: '스포츠'),
    _InterestOption(value: 'entertainment', label: '연예'),
  ];

  final TextEditingController _targetJobCtrl = TextEditingController();
  final TextEditingController _customCtrl = TextEditingController();
  final Set<String> _selected = <String>{};

  bool _saving = false;
  String? _error;

  @override
  void dispose() {
    _targetJobCtrl.dispose();
    _customCtrl.dispose();
    super.dispose();
  }

  void _toggleInterest(String value) {
    setState(() {
      if (_selected.contains(value)) {
        _selected.remove(value);
      } else {
        _selected.add(value);
      }
    });
  }

  void _addCustomInterest() {
    final v = _customCtrl.text.trim();
    if (v.isEmpty) return;
    if (_selected.contains(v)) return;
    setState(() {
      _selected.add(v);
      _customCtrl.clear();
    });
  }

  String? _labelFor(String value) {
    for (final o in _interestOptions) {
      if (o.value == value) return o.label;
    }
    return null;
  }

  Future<void> _submit() async {
    if (_saving) return;
    final job = _targetJobCtrl.text.trim();
    if (job.isEmpty) {
      setState(() => _error = '목표 직무를 입력해주세요.');
      return;
    }
    if (_selected.isEmpty) {
      setState(() => _error = '관심 키워드를 1개 이상 선택해주세요.');
      return;
    }

    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      final auth = ref.read(authServiceProvider);
      await auth.upsertSyncProfile(
        targetJob: job,
        interestKeywords: _selected.toList(),
      );
      if (!mounted) return;
      context.go('/');
    } catch (e) {
      setState(() => _error = '저장 실패: $e');
    } finally {
      if (mounted) {
        setState(() => _saving = false);
      }
    }
  }

  Future<void> _logout() async {
    if (_saving) return;
    final auth = ref.read(authServiceProvider);
    await auth.logout();
    if (!mounted) return;
    context.go('/login');
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(
        title: const Text('회원 정보 입력'),
        actions: [
          TextButton(
            onPressed: _saving ? null : _logout,
            child: const Text('로그아웃'),
          ),
        ],
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(20, 12, 20, 24),
          children: [
            Text(
              '환영합니다!',
              style: theme.textTheme.headlineSmall?.copyWith(
                fontWeight: FontWeight.w800,
              ),
            ),
            const SizedBox(height: 6),
            Text(
              '맞춤 인사이트를 위해 한 가지만 알려주세요. 언제든 마이페이지에서 변경할 수 있습니다.',
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onSurface.withValues(alpha: 0.7),
              ),
            ),
            const SizedBox(height: 24),

            _SectionLabel('목표 직무', required: true),
            const SizedBox(height: 8),
            TextField(
              controller: _targetJobCtrl,
              textInputAction: TextInputAction.next,
              decoration: const InputDecoration(
                hintText: '예) 백엔드 엔지니어, 데이터 분석가',
                border: OutlineInputBorder(),
              ),
            ),

            const SizedBox(height: 24),
            _SectionLabel('관심 키워드 (복수 선택 가능)', required: true),
            const SizedBox(height: 12),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: _interestOptions.map((o) {
                final selected = _selected.contains(o.value);
                return FilterChip(
                  label: Text(o.label),
                  selected: selected,
                  onSelected: (_) => _toggleInterest(o.value),
                );
              }).toList(),
            ),

            const SizedBox(height: 16),
            Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _customCtrl,
                    onSubmitted: (_) => _addCustomInterest(),
                    decoration: const InputDecoration(
                      hintText: '직접 입력 (예: 부동산)',
                      border: OutlineInputBorder(),
                      isDense: true,
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                FilledButton.tonal(
                  onPressed: _addCustomInterest,
                  child: const Text('추가'),
                ),
              ],
            ),

            if (_selected.isNotEmpty) ...[
              const SizedBox(height: 16),
              Text(
                '선택된 키워드',
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.onSurface.withValues(alpha: 0.6),
                ),
              ),
              const SizedBox(height: 8),
              Wrap(
                spacing: 6,
                runSpacing: 6,
                children: _selected
                    .map((v) => InputChip(
                          label: Text(_labelFor(v) ?? v),
                          onDeleted: () => setState(() => _selected.remove(v)),
                        ))
                    .toList(),
              ),
            ],

            const SizedBox(height: 28),
            FilledButton(
              onPressed: _saving ? null : _submit,
              style: FilledButton.styleFrom(
                minimumSize: const Size(double.infinity, 52),
              ),
              child: _saving
                  ? const SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Text('가입 완료'),
            ),
            if (_error != null) ...[
              const SizedBox(height: 12),
              Text(
                _error!,
                style: const TextStyle(color: Colors.redAccent),
                textAlign: TextAlign.center,
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _SectionLabel extends StatelessWidget {
  const _SectionLabel(this.text, {this.required = false});

  final String text;
  final bool required;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Row(
      children: [
        Text(
          text,
          style: theme.textTheme.titleSmall?.copyWith(
            fontWeight: FontWeight.w700,
          ),
        ),
        if (required) ...[
          const SizedBox(width: 4),
          const Text('*', style: TextStyle(color: Colors.redAccent)),
        ],
      ],
    );
  }
}

class _InterestOption {
  const _InterestOption({required this.value, required this.label});
  final String value;
  final String label;
}
