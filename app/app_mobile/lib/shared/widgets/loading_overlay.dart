import 'package:flutter/material.dart';

/// 전역 로딩 오버레이 placeholder — 추후 [OverlayPortal] 또는 라우터 observers와 연동.
class LoadingOverlay extends StatelessWidget {
  const LoadingOverlay({
    required this.loading,
    required this.child,
    super.key,
  });

  final bool loading;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Stack(
      children: [
        child,
        if (loading)
          const Positioned.fill(
            child: ColoredBox(
              color: Color(0x66000000),
              child: Center(child: CircularProgressIndicator()),
            ),
          ),
      ],
    );
  }
}
