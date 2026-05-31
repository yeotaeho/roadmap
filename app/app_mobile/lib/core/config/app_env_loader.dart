import 'package:flutter/services.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';

import 'env_parser.dart';
import 'filesystem_env_stub.dart'
    if (dart.library.io) 'filesystem_env_io.dart';

/// `dart_defines/local.env` SSOT 로드.
///
/// 우선순위 (낮음 → 높음, 뒤가 덮어씀):
/// 1. Monorepo 루트 `.env` (호스트 파일시스템)
/// 2. `dart_defines/local.env` (호스트 파일시스템)
/// 3. `dart_defines/local.env` (빌드 시 번들된 asset — **Android/iOS plain `flutter run`**)
///
/// compile-time `--dart-define-from-file` 은 [AppEnv] getter 에서 1순위로 적용.
Future<void> loadAppEnvFiles() async {
  final merged = <String, String>{};

  merged.addAll(await loadFilesystemEnvMaps());

  try {
    final bundled = await rootBundle.loadString('dart_defines/local.env');
    merged.addAll(parseEnvContent(bundled));
  } catch (_) {
    // local.env 가 없거나 pubspec asset 미등록 시 무시.
  }

  if (merged.isEmpty) {
    dotenv.loadFromString(envString: '', isOptional: true);
    return;
  }

  final envString = merged.entries.map((e) => '${e.key}=${e.value}').join('\n');
  dotenv.loadFromString(envString: envString);
}
