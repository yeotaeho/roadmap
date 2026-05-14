import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/auth/auth_service.dart';
import '../../../core/providers/core_providers.dart';

/// 내 프로필 화면.
///
/// - `GET /api/oauth/me` + `GET /api/user/sync-profile` 을 동시에 불러와 표시.
/// - 닉네임 / 목표 직무 / 관심 키워드를 한 화면에서 편집하고
///   "저장" 시 변경된 항목만 각각의 PUT 엔드포인트로 전송한다.
class ProfilePage extends ConsumerStatefulWidget {
  const ProfilePage({super.key});

  @override
  ConsumerState<ProfilePage> createState() => _ProfilePageState();
}

class _ProfilePageState extends ConsumerState<ProfilePage> {
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

  final TextEditingController _nameCtrl = TextEditingController();
  final TextEditingController _targetJobCtrl = TextEditingController();
  final TextEditingController _customCtrl = TextEditingController();
  final Set<String> _selected = <String>{};

  UserInfo? _initialUser;
  SyncProfile? _initialProfile;
  bool _loading = true;
  bool _saving = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _nameCtrl.dispose();
    _targetJobCtrl.dispose();
    _customCtrl.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    final auth = ref.read(authServiceProvider);
    final results = await Future.wait<dynamic>([
      auth.getMe(),
      auth.getSyncProfile(),
    ]);
    final user = results[0] as UserInfo?;
    final profile = results[1] as SyncProfile?;
    if (!mounted) return;
    setState(() {
      _initialUser = user;
      _initialProfile = profile;
      _nameCtrl.text = user?.displayName ?? '';
      _targetJobCtrl.text = profile?.targetJob ?? '';
      _selected
        ..clear()
        ..addAll(profile?.interestKeywords ?? const <String>[]);
      _loading = false;
    });
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
    final text = _customCtrl.text.trim();
    if (text.isEmpty) return;
    setState(() {
      _selected.add(text);
      _customCtrl.clear();
    });
  }

  String _labelFor(String value) {
    for (final o in _interestOptions) {
      if (o.value == value) return o.label;
    }
    return value;
  }

  Future<void> _save() async {
    if (_saving) return;
    final newName = _nameCtrl.text.trim();
    final newJob = _targetJobCtrl.text.trim();
    if (newName.isEmpty) {
      setState(() => _error = '닉네임은 비울 수 없습니다.');
      return;
    }
    if (newJob.isEmpty) {
      setState(() => _error = '목표 직무를 입력해주세요.');
      return;
    }
    if (_selected.isEmpty) {
      setState(() => _error = '관심 분야를 1개 이상 선택해주세요.');
      return;
    }

    setState(() {
      _saving = true;
      _error = null;
    });

    try {
      final auth = ref.read(authServiceProvider);
      final initialName = (_initialUser?.nickname?.trim().isNotEmpty ?? false)
          ? _initialUser!.nickname!.trim()
          : (_initialUser?.name?.trim() ?? '');
      final initialJob = _initialProfile?.targetJob ?? '';
      final initialKeywords = _initialProfile?.interestKeywords ?? const <String>[];
      final keywordsChanged = !_setEqual(_selected, initialKeywords.toSet());

      if (newName != initialName) {
        await auth.updateMe(name: newName);
      }
      if (newJob != initialJob || keywordsChanged) {
        await auth.upsertSyncProfile(
          targetJob: newJob,
          interestKeywords: _selected.toList(growable: false),
        );
      }

      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('프로필이 저장되었습니다.')),
      );
      await _load();
    } catch (e) {
      if (!mounted) return;
      setState(() => _error = '저장에 실패했습니다: $e');
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  bool _setEqual(Set<String> a, Set<String> b) {
    if (a.length != b.length) return false;
    return a.every(b.contains);
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final cs = theme.colorScheme;

    return Scaffold(
      appBar: AppBar(
        title: const Text('프로필'),
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : SafeArea(
              child: ListView(
                padding: const EdgeInsets.fromLTRB(20, 20, 20, 32),
                children: [
                  _ProfileHeader(user: _initialUser),
                  const SizedBox(height: 24),
                  const _SectionLabel(text: '닉네임'),
                  const SizedBox(height: 8),
                  TextField(
                    controller: _nameCtrl,
                    decoration: const InputDecoration(
                      hintText: '예) 청년인사이트',
                      border: OutlineInputBorder(),
                    ),
                    textInputAction: TextInputAction.next,
                  ),
                  if (_initialUser?.email != null) ...[
                    const SizedBox(height: 24),
                    const _SectionLabel(text: '이메일'),
                    const SizedBox(height: 8),
                    _ReadOnlyField(text: _initialUser!.email!),
                  ],
                  const SizedBox(height: 24),
                  const _SectionLabel(text: '목표 직무'),
                  const SizedBox(height: 8),
                  TextField(
                    controller: _targetJobCtrl,
                    decoration: const InputDecoration(
                      hintText: '예) 백엔드 개발자',
                      border: OutlineInputBorder(),
                    ),
                    textInputAction: TextInputAction.done,
                  ),
                  const SizedBox(height: 24),
                  const _SectionLabel(text: '관심 분야 (다중 선택)'),
                  const SizedBox(height: 12),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: [
                      ..._interestOptions.map((o) {
                        final selected = _selected.contains(o.value);
                        return FilterChip(
                          selected: selected,
                          label: Text(o.label),
                          onSelected: (_) => _toggleInterest(o.value),
                        );
                      }),
                      ..._selected
                          .where((v) => !_interestOptions.any((o) => o.value == v))
                          .map((v) => InputChip(
                                label: Text(_labelFor(v)),
                                onDeleted: () => _toggleInterest(v),
                              )),
                    ],
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Expanded(
                        child: TextField(
                          controller: _customCtrl,
                          decoration: const InputDecoration(
                            hintText: '직접 입력 (예: 헬스케어)',
                            isDense: true,
                            border: OutlineInputBorder(),
                          ),
                          onSubmitted: (_) => _addCustomInterest(),
                        ),
                      ),
                      const SizedBox(width: 8),
                      FilledButton.tonal(
                        onPressed: _addCustomInterest,
                        child: const Text('추가'),
                      ),
                    ],
                  ),
                  if (_error != null) ...[
                    const SizedBox(height: 16),
                    Text(
                      _error!,
                      style: TextStyle(color: cs.error),
                    ),
                  ],
                  const SizedBox(height: 24),
                  SizedBox(
                    height: 52,
                    child: FilledButton(
                      onPressed: _saving ? null : _save,
                      child: _saving
                          ? const SizedBox(
                              width: 20,
                              height: 20,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : const Text('저장하기'),
                    ),
                  ),
                ],
              ),
            ),
    );
  }
}

class _ProfileHeader extends StatelessWidget {
  const _ProfileHeader({required this.user});
  final UserInfo? user;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final cs = theme.colorScheme;
    final name = user?.displayName ?? '회원';
    final initial = name.characters.first.toUpperCase();
    final url = user?.profileImage;

    Widget avatar() {
      Widget fallback() => Container(
            width: 84,
            height: 84,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: cs.primary.withValues(alpha: 0.18),
              shape: BoxShape.circle,
            ),
            child: Text(
              initial,
              style: TextStyle(
                color: cs.primary,
                fontSize: 32,
                fontWeight: FontWeight.w800,
              ),
            ),
          );
      if (url == null || url.isEmpty) return fallback();
      return ClipOval(
        child: SizedBox(
          width: 84,
          height: 84,
          child: Image.network(
            url,
            fit: BoxFit.cover,
            errorBuilder: (context, error, stack) => fallback(),
          ),
        ),
      );
    }

    String? providerLabel() {
      final p = user?.provider;
      if (p == null || p.isEmpty) return null;
      return switch (p.toLowerCase()) {
        'google' => 'Google 계정으로 로그인',
        'kakao' => 'Kakao 계정으로 로그인',
        'naver' => 'Naver 계정으로 로그인',
        _ => '$p 계정으로 로그인',
      };
    }

    return Column(
      children: [
        avatar(),
        const SizedBox(height: 14),
        Text(
          name,
          style: theme.textTheme.titleLarge?.copyWith(
            fontWeight: FontWeight.w800,
          ),
        ),
        if (providerLabel() != null) ...[
          const SizedBox(height: 6),
          Text(
            providerLabel()!,
            style: theme.textTheme.bodySmall?.copyWith(
              color: cs.onSurfaceVariant,
            ),
          ),
        ],
      ],
    );
  }
}

class _SectionLabel extends StatelessWidget {
  const _SectionLabel({required this.text});
  final String text;

  @override
  Widget build(BuildContext context) {
    return Text(
      text,
      style: Theme.of(context)
          .textTheme
          .titleSmall
          ?.copyWith(fontWeight: FontWeight.w700),
    );
  }
}

class _ReadOnlyField extends StatelessWidget {
  const _ReadOnlyField({required this.text});
  final String text;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
      decoration: BoxDecoration(
        color: cs.surfaceContainerHighest.withValues(alpha: 0.6),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: cs.outlineVariant),
      ),
      child: Text(text),
    );
  }
}

class _InterestOption {
  const _InterestOption({required this.value, required this.label});
  final String value;
  final String label;
}
