import 'package:flutter/material.dart';

/// 인사이트 대시보드 (실시간 펄스·블루오션·싱크·찬스 L2 탭은 추후 세분화).
class DashboardPage extends StatelessWidget {
  const DashboardPage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('인사이트 대시보드')),
      body: const Center(
        child: Text(
          '실시간 펄스 · 블루오션 · 싱크로율 · 다이렉트 찬스',
          textAlign: TextAlign.center,
        ),
      ),
    );
  }
}
