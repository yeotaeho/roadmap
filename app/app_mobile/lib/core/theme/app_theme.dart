import 'package:flutter/material.dart';

import 'app_colors.dart';

abstract final class AppTheme {
  static ThemeData get light {
    final base = ThemeData(
      useMaterial3: true,
      colorScheme: ColorScheme.fromSeed(
        seedColor: AppColors.indigo600,
        brightness: Brightness.light,
        surface: AppColors.slate50,
      ),
    );
    return base.copyWith(
      appBarTheme: const AppBarTheme(centerTitle: false, elevation: 0),
      tabBarTheme: TabBarThemeData(
        labelColor: AppColors.indigo600,
        unselectedLabelColor: AppColors.slate900.withValues(alpha: 0.55),
        indicatorColor: AppColors.indigo600,
      ),
      navigationBarTheme: NavigationBarThemeData(
        indicatorColor: AppColors.indigo600.withValues(alpha: 0.12),
        labelTextStyle: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return const TextStyle(
              fontWeight: FontWeight.w600,
              color: AppColors.indigo600,
            );
          }
          return null;
        }),
      ),
    );
  }

  static ThemeData get dark {
    final base = ThemeData(
      useMaterial3: true,
      colorScheme: ColorScheme.fromSeed(
        seedColor: AppColors.indigo600,
        brightness: Brightness.dark,
        surface: AppColors.slate800,
        surfaceContainerLow: AppColors.slate700,
        surfaceContainerHigh: const Color(0xFF475569),
      ),
    );
    return base.copyWith(
      scaffoldBackgroundColor: AppColors.slate800,
      cardTheme: CardThemeData(
        color: AppColors.slate700.withValues(alpha: 0.65),
        elevation: 0,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      ),
      appBarTheme: const AppBarTheme(centerTitle: false, elevation: 0),
      tabBarTheme: TabBarThemeData(
        labelColor: base.colorScheme.primary,
        unselectedLabelColor: Colors.white70,
        indicatorColor: base.colorScheme.primary,
      ),
      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: AppColors.slate900,
        indicatorColor: AppColors.indigo600.withValues(alpha: 0.2),
        surfaceTintColor: Colors.transparent,
        labelTextStyle: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return const TextStyle(
              fontWeight: FontWeight.w600,
              color: AppColors.indigo600,
            );
          }
          return TextStyle(color: Colors.white.withValues(alpha: 0.65));
        }),
      ),
    );
  }
}
