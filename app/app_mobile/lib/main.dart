import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'core/config/app_env.dart';
import 'core/router/app_router.dart';
import 'core/theme/app_theme.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await AppEnv.load();
  runApp(
    const ProviderScope(
      child: YouthInsightApp(),
    ),
  );
}

class YouthInsightApp extends StatelessWidget {
  const YouthInsightApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(
      title: '청년 인사이트',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light,
      darkTheme: AppTheme.dark,
      themeMode: ThemeMode.system,
      routerConfig: appRouter,
    );
  }
}
