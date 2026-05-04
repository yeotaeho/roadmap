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
        surface: AppColors.slate950,
      ),
    );
    return base.copyWith(
      scaffoldBackgroundColor: AppColors.slate950,
      appBarTheme: const AppBarTheme(centerTitle: false, elevation: 0),
    );
  }
}
