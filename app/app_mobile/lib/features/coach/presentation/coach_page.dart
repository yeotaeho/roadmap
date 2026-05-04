import 'package:flutter/material.dart';
import 'package:flutter_markdown_plus/flutter_markdown_plus.dart';

/// AI 코치 — 대화 + Insight Wallet (추후). 마크다운은 유지보수 중인 **flutter_markdown_plus** 사용.
class CoachPage extends StatelessWidget {
  const CoachPage({super.key});

  static const _demoMarkdown = '''
**Daily Mentor** 데모 응답입니다.

```dart
void main() {
  runApp(const ProviderScope(child: MyApp()));
}
```

- GFM 코드 펜스 지원 → 이후 `syntaxHighlighter`로 하이라이팅 확장 가능  
- 길게 탭하여 복사는 `selectable: true` 등으로 조정 가능합니다.
''';

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('AI 코치')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          MarkdownBody(
            data: _demoMarkdown,
            selectable: true,
            styleSheet: MarkdownStyleSheet.fromTheme(Theme.of(context)).copyWith(
              code: TextStyle(
                fontFamily: 'monospace',
                backgroundColor: Theme.of(context).colorScheme.surfaceContainerHighest,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
