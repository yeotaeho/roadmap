import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:app_mobile/core/config/app_env.dart';
import 'package:app_mobile/main.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('앱 기동 후 비로그인 시 로그인 화면 도달', (WidgetTester tester) async {
    await AppEnv.load();
    await tester.pumpWidget(
      const ProviderScope(
        child: YouthInsightApp(),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.textContaining('청년 인사이트 로그인'), findsOneWidget);
  });
}
