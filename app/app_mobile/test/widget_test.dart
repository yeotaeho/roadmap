import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:app_mobile/core/config/app_env.dart';
import 'package:app_mobile/main.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('앱 기동 및 인사이트 탭 라벨 노출', (WidgetTester tester) async {
    await AppEnv.load();
    await tester.pumpWidget(
      const ProviderScope(
        child: YouthInsightApp(),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('인사이트'), findsOneWidget);
  });
}
