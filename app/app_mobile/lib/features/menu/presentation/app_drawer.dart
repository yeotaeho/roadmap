import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/auth/auth_service.dart';
import '../../../core/providers/core_providers.dart';

/// 대시보드(인사이트) 화면 우측에서 슬라이드되어 나오는 사용자 메뉴.
///
/// Flutter 의 `Scaffold.endDrawer` 슬롯에 배치하면 자동으로
/// 우측 → 좌측 방향으로 슬라이드 인 됩니다.
class AppDrawer extends ConsumerStatefulWidget {
  const AppDrawer({super.key});

  @override
  ConsumerState<AppDrawer> createState() => _AppDrawerState();
}

class _AppDrawerState extends ConsumerState<AppDrawer> {
  UserInfo? _user;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final auth = ref.read(authServiceProvider);
    final user = await auth.getMe();
    if (!mounted) return;
    setState(() {
      _user = user;
      _loading = false;
    });
  }

  Future<void> _logout() async {
    final theme = Theme.of(context);
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('로그아웃'),
        content: const Text('정말 로그아웃 하시겠어요?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('취소'),
          ),
          FilledButton.tonal(
            style: FilledButton.styleFrom(
              backgroundColor: theme.colorScheme.errorContainer,
              foregroundColor: theme.colorScheme.onErrorContainer,
            ),
            onPressed: () => Navigator.of(ctx).pop(true),
            child: const Text('로그아웃'),
          ),
        ],
      ),
    );
    if (ok != true || !mounted) return;
    final auth = ref.read(authServiceProvider);
    await auth.logout();
    if (!mounted) return;
    Navigator.of(context).pop();
    context.go('/login');
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final cs = theme.colorScheme;

    return Drawer(
      backgroundColor: cs.surface,
      child: SafeArea(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            _Header(user: _user, loading: _loading, onTapEdit: () {
              Navigator.of(context).pop();
              context.push('/profile');
            }),
            const Divider(height: 1),
            Expanded(
              child: ListView(
                padding: const EdgeInsets.symmetric(vertical: 8),
                children: [
                  _MenuTile(
                    icon: Icons.person_outline,
                    label: '프로필',
                    subtitle: '내 정보 · 직무 · 관심분야 관리',
                    onTap: () {
                      Navigator.of(context).pop();
                      context.push('/profile');
                    },
                  ),
                  _MenuTile(
                    icon: Icons.settings_outlined,
                    label: '설정',
                    subtitle: '테마 · 알림 · 계정',
                    onTap: () {
                      Navigator.of(context).pop();
                      context.push('/settings');
                    },
                  ),
                  _MenuTile(
                    icon: Icons.campaign_outlined,
                    label: '공지사항',
                    subtitle: '서비스 업데이트 소식',
                    onTap: () {
                      Navigator.of(context).pop();
                      context.push('/notices');
                    },
                  ),
                  _MenuTile(
                    icon: Icons.help_outline,
                    label: '도움말',
                    subtitle: '자주 묻는 질문 · 문의',
                    onTap: () {
                      Navigator.of(context).pop();
                      context.push('/help');
                    },
                  ),
                ],
              ),
            ),
            const Divider(height: 1),
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 16),
              child: SizedBox(
                width: double.infinity,
                child: OutlinedButton.icon(
                  onPressed: _logout,
                  icon: const Icon(Icons.logout),
                  label: const Text('로그아웃'),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _Header extends StatelessWidget {
  const _Header({
    required this.user,
    required this.loading,
    required this.onTapEdit,
  });

  final UserInfo? user;
  final bool loading;
  final VoidCallback onTapEdit;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final cs = theme.colorScheme;
    final providerLabel = _providerLabel(user?.provider);

    return InkWell(
      onTap: onTapEdit,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(20, 24, 16, 20),
        child: Row(
          children: [
            _Avatar(url: user?.profileImage, name: user?.displayName),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  if (loading)
                    SizedBox(
                      height: 16,
                      width: 120,
                      child: LinearProgressIndicator(
                        backgroundColor: cs.surfaceContainerHighest,
                      ),
                    )
                  else
                    Text(
                      user?.displayName ?? '게스트',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: theme.textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  const SizedBox(height: 4),
                  Text(
                    user?.email ?? (loading ? '' : '이메일 정보 없음'),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: cs.onSurfaceVariant,
                    ),
                  ),
                  if (providerLabel != null) ...[
                    const SizedBox(height: 6),
                    Container(
                      padding:
                          const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                      decoration: BoxDecoration(
                        color: cs.primary.withValues(alpha: 0.12),
                        borderRadius: BorderRadius.circular(999),
                      ),
                      child: Text(
                        providerLabel,
                        style: theme.textTheme.labelSmall?.copyWith(
                          color: cs.primary,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ),
                  ],
                ],
              ),
            ),
            const Icon(Icons.chevron_right),
          ],
        ),
      ),
    );
  }

  String? _providerLabel(String? provider) {
    if (provider == null || provider.isEmpty) return null;
    return switch (provider.toLowerCase()) {
      'google' => 'Google 로그인',
      'kakao' => 'Kakao 로그인',
      'naver' => 'Naver 로그인',
      _ => '$provider 로그인',
    };
  }
}

class _Avatar extends StatelessWidget {
  const _Avatar({required this.url, required this.name});

  final String? url;
  final String? name;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final initial = (name == null || name!.isEmpty) ? '?' : name!.characters.first.toUpperCase();
    final bg = cs.primary.withValues(alpha: 0.18);
    Widget fallback() => Container(
          width: 52,
          height: 52,
          alignment: Alignment.center,
          decoration: BoxDecoration(color: bg, shape: BoxShape.circle),
          child: Text(
            initial,
            style: TextStyle(
              color: cs.primary,
              fontSize: 22,
              fontWeight: FontWeight.w700,
            ),
          ),
        );

    if (url == null || url!.isEmpty) return fallback();
    return ClipOval(
      child: SizedBox(
        width: 52,
        height: 52,
        child: Image.network(
          url!,
          fit: BoxFit.cover,
          errorBuilder: (context, error, stack) => fallback(),
        ),
      ),
    );
  }
}

class _MenuTile extends StatelessWidget {
  const _MenuTile({
    required this.icon,
    required this.label,
    required this.subtitle,
    required this.onTap,
  });

  final IconData icon;
  final String label;
  final String subtitle;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return ListTile(
      leading: Container(
        width: 38,
        height: 38,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: cs.primary.withValues(alpha: 0.12),
          borderRadius: BorderRadius.circular(10),
        ),
        child: Icon(icon, color: cs.primary, size: 20),
      ),
      title: Text(label, style: const TextStyle(fontWeight: FontWeight.w600)),
      subtitle: Text(subtitle),
      trailing: const Icon(Icons.chevron_right, size: 20),
      onTap: onTap,
    );
  }
}
