import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../../core/providers/core_providers.dart';
import '../../../core/theme/theme_mode_controller.dart';

/// 앱 설정 화면.
///
/// 다음 항목을 다룹니다:
/// - 외관(테마): system / light / dark
/// - 알림 토글 (로컬 저장)
/// - 언어 (현재는 한국어 고정 — 표시만)
/// - 캐시 비우기 (간단 plotly 가 아닌 [SharedPreferences] 의 비-인증 키만 정리)
/// - 로그아웃
/// - 앱 정보(버전)
class SettingsPage extends ConsumerStatefulWidget {
  const SettingsPage({super.key});

  @override
  ConsumerState<SettingsPage> createState() => _SettingsPageState();
}

class _SettingsPageState extends ConsumerState<SettingsPage> {
  static const _kNotifPushKey = 'app.notif.push';
  static const _kNotifReportKey = 'app.notif.report';

  bool _notifPush = true;
  bool _notifReport = true;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    _restorePrefs();
  }

  Future<void> _restorePrefs() async {
    final prefs = await SharedPreferences.getInstance();
    if (!mounted) return;
    setState(() {
      _notifPush = prefs.getBool(_kNotifPushKey) ?? true;
      _notifReport = prefs.getBool(_kNotifReportKey) ?? true;
    });
  }

  Future<void> _setBoolPref(String key, bool value) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(key, value);
  }

  Future<void> _pickThemeMode() async {
    final current = ref.read(themeModeProvider);
    final picked = await showModalBottomSheet<ThemeMode>(
      context: context,
      builder: (ctx) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(
              leading: const Icon(Icons.brightness_auto_outlined),
              title: const Text('시스템 설정 따르기'),
              trailing: current == ThemeMode.system ? const Icon(Icons.check) : null,
              onTap: () => Navigator.of(ctx).pop(ThemeMode.system),
            ),
            ListTile(
              leading: const Icon(Icons.light_mode_outlined),
              title: const Text('라이트'),
              trailing: current == ThemeMode.light ? const Icon(Icons.check) : null,
              onTap: () => Navigator.of(ctx).pop(ThemeMode.light),
            ),
            ListTile(
              leading: const Icon(Icons.dark_mode_outlined),
              title: const Text('다크'),
              trailing: current == ThemeMode.dark ? const Icon(Icons.check) : null,
              onTap: () => Navigator.of(ctx).pop(ThemeMode.dark),
            ),
            const SizedBox(height: 8),
          ],
        ),
      ),
    );
    if (picked != null) {
      await ref.read(themeModeProvider.notifier).setMode(picked);
    }
  }

  Future<void> _pickLanguage() async {
    await showDialog<void>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('언어'),
        content: const Text(
          '현재는 한국어만 지원합니다.\n다국어 지원은 추후 업데이트 예정입니다.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(),
            child: const Text('확인'),
          ),
        ],
      ),
    );
  }

  Future<void> _clearCache() async {
    setState(() => _busy = true);
    try {
      final prefs = await SharedPreferences.getInstance();
      // 인증/테마/알림 같은 사용자 설정은 유지하고, 캐시 성격 키만 삭제.
      // 현재 프로젝트는 명시적인 캐시 키가 없으므로, 향후 도입 시 prefix 'cache.' 로 통일 권장.
      final keys = prefs.getKeys().where((k) => k.startsWith('cache.')).toList();
      for (final k in keys) {
        await prefs.remove(k);
      }
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('캐시 ${keys.length}개 항목을 비웠습니다.')),
      );
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _logout() async {
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
          FilledButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            child: const Text('로그아웃'),
          ),
        ],
      ),
    );
    if (ok != true) return;
    setState(() => _busy = true);
    try {
      await ref.read(authServiceProvider).logout();
      if (!mounted) return;
      context.go('/login');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _confirmDelete() async {
    await showDialog<void>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('회원 탈퇴'),
        content: const Text(
          '회원 탈퇴 기능은 준비 중입니다.\n탈퇴를 원하시면 [도움말 > 문의하기] 를 이용해 주세요.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(),
            child: const Text('확인'),
          ),
        ],
      ),
    );
  }

  String _modeLabel(ThemeMode m) => switch (m) {
        ThemeMode.system => '시스템 설정 따르기',
        ThemeMode.light => '라이트',
        ThemeMode.dark => '다크',
      };

  @override
  Widget build(BuildContext context) {
    final mode = ref.watch(themeModeProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('설정'),
      ),
      body: ListView(
        children: [
          _SectionTitle(label: '외관'),
          ListTile(
            leading: const Icon(Icons.palette_outlined),
            title: const Text('테마'),
            subtitle: Text(_modeLabel(mode)),
            trailing: const Icon(Icons.chevron_right),
            onTap: _pickThemeMode,
          ),
          const Divider(height: 1),
          _SectionTitle(label: '알림'),
          SwitchListTile(
            secondary: const Icon(Icons.notifications_active_outlined),
            title: const Text('일반 알림'),
            subtitle: const Text('서비스 공지·업데이트 알림 수신'),
            value: _notifPush,
            onChanged: (v) async {
              setState(() => _notifPush = v);
              await _setBoolPref(_kNotifPushKey, v);
            },
          ),
          SwitchListTile(
            secondary: const Icon(Icons.insights_outlined),
            title: const Text('주간 인사이트 리포트'),
            subtitle: const Text('월요일 오전 8시 발송'),
            value: _notifReport,
            onChanged: (v) async {
              setState(() => _notifReport = v);
              await _setBoolPref(_kNotifReportKey, v);
            },
          ),
          const Divider(height: 1),
          _SectionTitle(label: '일반'),
          ListTile(
            leading: const Icon(Icons.translate_outlined),
            title: const Text('언어'),
            subtitle: const Text('한국어'),
            trailing: const Icon(Icons.chevron_right),
            onTap: _pickLanguage,
          ),
          ListTile(
            leading: const Icon(Icons.cleaning_services_outlined),
            title: const Text('캐시 비우기'),
            subtitle: const Text('임시 저장된 데이터를 삭제합니다.'),
            onTap: _busy ? null : _clearCache,
          ),
          const Divider(height: 1),
          _SectionTitle(label: '계정'),
          ListTile(
            leading: const Icon(Icons.logout),
            title: const Text('로그아웃'),
            onTap: _busy ? null : _logout,
          ),
          ListTile(
            leading: Icon(Icons.delete_outline, color: Theme.of(context).colorScheme.error),
            title: Text(
              '회원 탈퇴',
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
            onTap: _busy ? null : _confirmDelete,
          ),
          const Divider(height: 1),
          _SectionTitle(label: '앱 정보'),
          const ListTile(
            leading: Icon(Icons.info_outline),
            title: Text('버전'),
            subtitle: Text('1.0.0 (1)'),
          ),
          const ListTile(
            leading: Icon(Icons.description_outlined),
            title: Text('이용약관'),
            trailing: Icon(Icons.chevron_right),
          ),
          const ListTile(
            leading: Icon(Icons.privacy_tip_outlined),
            title: Text('개인정보처리방침'),
            trailing: Icon(Icons.chevron_right),
          ),
          const SizedBox(height: 24),
        ],
      ),
    );
  }
}

class _SectionTitle extends StatelessWidget {
  const _SectionTitle({required this.label});
  final String label;

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 20, 16, 8),
      child: Text(
        label,
        style: TextStyle(
          color: cs.primary,
          fontSize: 12,
          fontWeight: FontWeight.w800,
          letterSpacing: 0.5,
        ),
      ),
    );
  }
}
