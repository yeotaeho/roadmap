import 'package:flutter/material.dart';

import '../../menu/presentation/app_drawer.dart';
import 'tabs/chance_tab.dart';
import 'tabs/gap_tab.dart';
import 'tabs/pulse_tab.dart';
import 'tabs/sync_tab.dart';

/// 인사이트 대시보드 — L2 4탭(설계서: pulse / gap / sync / chance).
class DashboardPage extends StatefulWidget {
  const DashboardPage({super.key});

  @override
  State<DashboardPage> createState() => _DashboardPageState();
}

class _DashboardPageState extends State<DashboardPage>
    with SingleTickerProviderStateMixin {
  late final TabController _tabController;
  final GlobalKey<ScaffoldState> _scaffoldKey = GlobalKey<ScaffoldState>();

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 4, vsync: this);
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      key: _scaffoldKey,
      endDrawer: const AppDrawer(),
      appBar: AppBar(
        title: const Text('인사이트 대시보드'),
        actions: [
          IconButton(
            tooltip: '메뉴 열기',
            icon: const Icon(Icons.menu),
            onPressed: () => _scaffoldKey.currentState?.openEndDrawer(),
          ),
          const SizedBox(width: 4),
        ],
        bottom: TabBar(
          controller: _tabController,
          isScrollable: true,
          tabAlignment: TabAlignment.start,
          tabs: const [
            Tab(text: '펄스'),
            Tab(text: '블루오션'),
            Tab(text: '싱크'),
            Tab(text: '찬스'),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: const [
          PulseTab(),
          GapTab(),
          SyncTab(),
          ChanceTab(),
        ],
      ),
    );
  }
}
