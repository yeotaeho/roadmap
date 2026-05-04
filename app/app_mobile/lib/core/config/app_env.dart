import 'package:flutter/foundation.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';

import 'root_env_loader.dart';

/// 환경 변수 해석 순서 (높은 우선순위 먼저):
/// 1. `--dart-define=API_BASE_URL=...`
/// 2. 리포지토리 루트 — `docker-compose.yaml`(또는 `.yml`)과 같은 폴더의 `.env`
///    (`flutter run` 시 보통 `Directory.current` 기준 상위 탐색으로 발견)
/// 3. 기본 플레이스홀더 URL
///
/// 실제 단말(iOS/Android) 릴리스 빌드에서는 루트 `.env` 경로가 없을 수 있으므로
/// CI/스토어 빌드에는 `--dart-define` 또는 프로덕션 전용 설정을 권장합니다.
abstract final class AppEnv {
  static var _loadAttempted = false;

  /// `main()`에서 `runApp` 전에 한 번 호출.
  static Future<void> load() async {
    if (_loadAttempted) return;
    _loadAttempted = true;
    try {
      await loadRepoRootDotEnv();
      if (kDebugMode) {
        debugPrint('[AppEnv] API_BASE_URL → $apiBaseUrl');
      }
    } catch (e, st) {
      if (kDebugMode) {
        debugPrint('[AppEnv] 루트 .env 로드 실패: $e\n$st');
      }
      dotenv.loadFromString(envString: '', isOptional: true);
    }
  }

  static String get apiBaseUrl {
    const fromDefine = String.fromEnvironment(
      'API_BASE_URL',
      defaultValue: '',
    );
    if (fromDefine.isNotEmpty) return fromDefine;

    if (dotenv.isInitialized) {
      final fromFile = dotenv.env['API_BASE_URL']?.trim();
      if (fromFile != null && fromFile.isNotEmpty) return fromFile;
    }

    return 'https://api.example.com';
  }
}
