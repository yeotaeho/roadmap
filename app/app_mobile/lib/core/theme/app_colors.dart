import 'package:flutter/material.dart';

/// 웹(Next.js)과 동일한 인디고·슬레이트 베이스 토큰.
abstract final class AppColors {
  static const Color indigo600 = Color(0xFF4F46E5);
  static const Color indigo700 = Color(0xFF4338CA);
  /// 분야 트렌드 카드 공통 — 스코어·뱃지·게이지 등 지표 색(참조 `#6366F1`).
  static const Color sectorMetricAccent = Color(0xFF6366F1);
  static const Color slate50 = Color(0xFFF8FAFC);
  /// 다크 셸 배경(웹 트레이딩 터미널 톤에 맞춘 슬레이트).
  static const Color slate800 = Color(0xFF1E293B);
  static const Color slate700 = Color(0xFF334155);
  static const Color slate900 = Color(0xFF0F172A);
  static const Color slate950 = Color(0xFF020617);

  /// 싱크·찬스 탭 카드 면 (참조 `#333F50`).
  static const Color syncChanceCardSurface = Color(0xFF333F50);

  /// 게이지 **미채움** 트랙 — 카드 배경·액센트 채움과 구분되는 어두운 면(살짝 같은 색조).
  /// 채움(`LinearProgressIndicator.color`)은 반드시 `accent`로 두고, 배경과 섞이지 않게 할 때 사용.
  static Color gaugeTrackForAccent(Color accent) {
    const base = Color(0xFF0F172A);
    return Color.alphaBlend(accent.withValues(alpha: 0.2), base);
  }
}
