import 'package:flutter/material.dart';

/// 전략 로드맵 — 여정 개요 / 성장 아카이브 서브탭은 추후 [TabBar]로 분리.
class RoadmapPage extends StatelessWidget {
  const RoadmapPage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('전략 로드맵')),
      body: const Center(
        child: Text('퀘스트 트리 · 성장 아카이브(캘린더)'),
      ),
    );
  }
}
