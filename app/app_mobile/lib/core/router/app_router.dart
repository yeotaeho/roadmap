import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../auth/auth_service.dart';
import '../auth/token_storage.dart';
import '../../features/auth/presentation/auth_gate_page.dart';
import '../../features/auth/presentation/login_page.dart';
import '../../features/auth/presentation/signup_complete_page.dart';
import '../../features/coach/presentation/coach_page.dart';
import '../../features/consult/presentation/consult_page.dart';
import '../../features/dashboard/presentation/dashboard_page.dart';
import '../../features/dashboard/presentation/detail/chance_detail_page.dart';
import '../../features/dashboard/presentation/detail/gap_issue_detail_page.dart';
import '../../features/dashboard/presentation/detail/sector_detail_page.dart';
import '../../features/help/presentation/help_page.dart';
import '../../features/notice/presentation/notices_page.dart';
import '../../features/profile/presentation/profile_page.dart';
import '../../features/roadmap/presentation/roadmap_page.dart';
import '../../features/settings/presentation/settings_page.dart';

final GlobalKey<NavigatorState> rootNavigatorKey =
    GlobalKey<NavigatorState>(debugLabel: 'root');

/// Next.js 메인 탭과 동일한 경로: `/`, `/consult`, `/roadmap`, `/coach`
final GoRouter appRouter = GoRouter(
  navigatorKey: rootNavigatorKey,
  initialLocation: '/auth-gate',
  routes: [
    GoRoute(
      path: '/auth-gate',
      name: 'auth-gate',
      pageBuilder: (context, state) => const NoTransitionPage<void>(
        child: AuthGatePage(),
      ),
    ),
    GoRoute(
      path: '/login',
      name: 'login',
      pageBuilder: (context, state) => const NoTransitionPage<void>(
        child: LoginPage(),
      ),
    ),
    GoRoute(
      path: '/signup-complete',
      name: 'signup-complete',
      pageBuilder: (context, state) => const NoTransitionPage<void>(
        child: SignupCompletePage(),
      ),
    ),
    GoRoute(
      path: '/profile',
      name: 'profile',
      builder: (context, state) => const ProfilePage(),
    ),
    GoRoute(
      path: '/settings',
      name: 'settings',
      builder: (context, state) => const SettingsPage(),
    ),
    GoRoute(
      path: '/notices',
      name: 'notices',
      builder: (context, state) => const NoticesPage(),
    ),
    GoRoute(
      path: '/help',
      name: 'help',
      builder: (context, state) => const HelpPage(),
    ),
    StatefulShellRoute.indexedStack(
      builder: (context, state, navigationShell) {
        return MainTabScaffold(navigationShell: navigationShell);
      },
      branches: [
        StatefulShellBranch(
          routes: [
            GoRoute(
              path: '/',
              name: 'dashboard',
              pageBuilder: (context, state) => const NoTransitionPage<void>(
                child: DashboardPage(),
              ),
              routes: [
                GoRoute(
                  path: 'pulse/sectors/:slug',
                  parentNavigatorKey: rootNavigatorKey,
                  builder: (context, state) => SectorDetailPage(
                    slug: state.pathParameters['slug']!,
                  ),
                ),
                GoRoute(
                  path: 'gap/issues/:issueId',
                  parentNavigatorKey: rootNavigatorKey,
                  builder: (context, state) => GapIssueDetailPage(
                    issueId: state.pathParameters['issueId']!,
                  ),
                ),
                GoRoute(
                  path: 'chance/opportunities/:opportunityId',
                  parentNavigatorKey: rootNavigatorKey,
                  builder: (context, state) => ChanceDetailPage(
                    opportunityId: state.pathParameters['opportunityId']!,
                  ),
                ),
              ],
            ),
          ],
        ),
        StatefulShellBranch(
          routes: [
            GoRoute(
              path: '/consult',
              name: 'consult',
              pageBuilder: (context, state) => const NoTransitionPage<void>(
                child: ConsultPage(),
              ),
            ),
          ],
        ),
        StatefulShellBranch(
          routes: [
            GoRoute(
              path: '/roadmap',
              name: 'roadmap',
              pageBuilder: (context, state) => const NoTransitionPage<void>(
                child: RoadmapPage(),
              ),
            ),
          ],
        ),
        StatefulShellBranch(
          routes: [
            GoRoute(
              path: '/coach',
              name: 'coach',
              pageBuilder: (context, state) => const NoTransitionPage<void>(
                child: CoachPage(),
              ),
            ),
          ],
        ),
      ],
    ),
  ],
);

class MainTabScaffold extends StatefulWidget {
  const MainTabScaffold({
    required this.navigationShell,
    super.key,
  });

  final StatefulNavigationShell navigationShell;

  @override
  State<MainTabScaffold> createState() => _MainTabScaffoldState();
}

class _MainTabScaffoldState extends State<MainTabScaffold> {
  final TokenStorage _tokenStorage = TokenStorage();
  late final AuthService _authService = AuthService(storage: _tokenStorage);
  bool _hasSession = false;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    _refreshAuthState();
  }

  Future<void> _refreshAuthState() async {
    final access = await _tokenStorage.readAccessToken();
    final refresh = await _tokenStorage.readRefreshToken();
    if (!mounted) return;
    setState(() {
      _hasSession =
          (access != null && access.isNotEmpty) ||
          (refresh != null && refresh.isNotEmpty);
    });
  }

  Future<void> _logout() async {
    if (_busy) return;
    setState(() => _busy = true);
    await _authService.logout();
    if (!mounted) return;
    setState(() {
      _busy = false;
      _hasSession = false;
    });
    if (mounted) {
      context.go('/login');
    }
  }

  void _onTap(int index) {
    widget.navigationShell.goBranch(
      index,
      initialLocation: index == widget.navigationShell.currentIndex,
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      body: widget.navigationShell,
      floatingActionButton: FloatingActionButton.small(
        heroTag: 'auth-status-fab',
        onPressed: () {
          showModalBottomSheet<void>(
            context: context,
            backgroundColor: theme.colorScheme.surface,
            builder: (ctx) {
              return SafeArea(
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(16, 14, 16, 20),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        '인증 상태',
                        style: theme.textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      const SizedBox(height: 12),
                      Row(
                        children: [
                          Icon(
                            Icons.circle,
                            size: 10,
                            color: _hasSession ? Colors.greenAccent : Colors.redAccent,
                          ),
                          const SizedBox(width: 8),
                          Text(
                            _hasSession ? '로그인됨' : '세션 없음',
                            style: theme.textTheme.bodyMedium,
                          ),
                          const Spacer(),
                          TextButton.icon(
                            onPressed: _busy ? null : _refreshAuthState,
                            icon: const Icon(Icons.refresh, size: 16),
                            label: const Text('새로고침'),
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      SizedBox(
                        width: double.infinity,
                        child: FilledButton.icon(
                          onPressed: (_busy || !_hasSession)
                              ? null
                              : () async {
                                  Navigator.of(ctx).pop();
                                  await _logout();
                                },
                          icon: _busy
                              ? const SizedBox(
                                  width: 16,
                                  height: 16,
                                  child: CircularProgressIndicator(strokeWidth: 2),
                                )
                              : const Icon(Icons.logout),
                          label: const Text('로그아웃'),
                        ),
                      ),
                    ],
                  ),
                ),
              );
            },
          );
        },
        child: Icon(
          _hasSession ? Icons.verified_user : Icons.person_off,
        ),
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: widget.navigationShell.currentIndex,
        onDestinationSelected: _onTap,
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.dashboard_outlined),
            selectedIcon: Icon(Icons.dashboard),
            label: '인사이트',
          ),
          NavigationDestination(
            icon: Icon(Icons.chat_bubble_outline),
            selectedIcon: Icon(Icons.chat_bubble),
            label: '상담',
          ),
          NavigationDestination(
            icon: Icon(Icons.map_outlined),
            selectedIcon: Icon(Icons.map),
            label: '로드맵',
          ),
          NavigationDestination(
            icon: Icon(Icons.auto_awesome_outlined),
            selectedIcon: Icon(Icons.auto_awesome),
            label: '코치',
          ),
        ],
        labelBehavior: NavigationDestinationLabelBehavior.alwaysShow,
        indicatorColor: theme.colorScheme.primary.withValues(alpha: 0.15),
      ),
    );
  }
}
