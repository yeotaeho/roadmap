import 'package:flutter/material.dart';

/// AI 상담실 — 채팅 캔버스 + 라이브 분석 패널 (Recharts → fl_chart).
class ConsultPage extends StatelessWidget {
  const ConsultPage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('AI 상담실')),
      body: const Center(child: Text('Deep Discovery 세션 · 레이더 차트 영역')),
    );
  }
}
