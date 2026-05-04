import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../features/coach/presentation/coach_page.dart';
import '../../features/consult/presentation/consult_page.dart';
import '../../features/dashboard/presentation/dashboard_page.dart';
import '../../features/roadmap/presentation/roadmap_page.dart';

final GlobalKey<NavigatorState> rootNavigatorKey =
    GlobalKey<NavigatorState>(debugLabel: 'root');

/// Next.js 메인 탭과 동일한 경로: `/`, `/consult`, `/roadmap`, `/coach`
final GoRouter appRouter = GoRouter(
  navigatorKey: rootNavigatorKey,
  initialLocation: '/',
  routes: [
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

class MainTabScaffold extends StatelessWidget {
  const MainTabScaffold({
    required this.navigationShell,
    super.key,
  });

  final StatefulNavigationShell navigationShell;

  void _onTap(int index) {
    navigationShell.goBranch(
      index,
      initialLocation: index == navigationShell.currentIndex,
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      body: navigationShell,
      bottomNavigationBar: NavigationBar(
        selectedIndex: navigationShell.currentIndex,
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
