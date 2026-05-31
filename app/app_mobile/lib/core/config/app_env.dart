import 'package:flutter_dotenv/flutter_dotenv.dart';

import 'root_env_loader.dart';

/// 환경 변수 해석 순서 (높은 우선순위 먼저):
/// 1. `--dart-define=...` / `--dart-define-from-file` (compile-time, 선택)
/// 2. `dart_defines/local.env` asset (빌드 시 APK/IPA에 포함 → **plain `flutter run` OK**)
/// 3. `dart_defines/local.env` / Monorepo 루트 `.env` (호스트 파일시스템, dev·test)
/// 4. 기본값
abstract final class AppEnv {
  static const localEnvRelativePath = 'dart_defines/local.env';

  static var _loadAttempted = false;

  /// `main()`에서 `runApp` 전에 한 번 호출.
  static Future<void> load() async {
    if (_loadAttempted) return;
    _loadAttempted = true;
    try {
      await loadAppEnvFiles();
    } catch (_) {
      dotenv.loadFromString(envString: '', isOptional: true);
    }
  }

  /// compile-time dart-define + runtime dotenv 모두 비어 있으면 true.
  static bool get isGoogleServerClientIdMissing {
    const fromDefine = String.fromEnvironment(
      'GOOGLE_SERVER_CLIENT_ID',
      defaultValue: '',
    );
    if (fromDefine.isNotEmpty) return false;
    if (dotenv.isInitialized) {
      final fromFile = dotenv.env['GOOGLE_SERVER_CLIENT_ID']?.trim();
      if (fromFile != null && fromFile.isNotEmpty) return false;
    }
    return true;
  }

  static String get apiBaseUrl {
    const fromDefine = String.fromEnvironment(
      'API_BASE_URL',
      defaultValue: '',
    );
    if (fromDefine.isNotEmpty) return _normalizeUrl(fromDefine);

    if (dotenv.isInitialized) {
      final fromFile = dotenv.env['API_BASE_URL']?.trim();
      if (fromFile != null && fromFile.isNotEmpty) return _normalizeUrl(fromFile);
    }

    return 'http://10.0.2.2:8000';
  }

  static String? get googleServerClientId {
    const fromDefine = String.fromEnvironment(
      'GOOGLE_SERVER_CLIENT_ID',
      defaultValue: '',
    );
    if (fromDefine.isNotEmpty) return fromDefine.trim();
    if (dotenv.isInitialized) {
      final fromFile = dotenv.env['GOOGLE_SERVER_CLIENT_ID']?.trim();
      if (fromFile != null && fromFile.isNotEmpty) return fromFile;
    }
    return null;
  }

  /// 카카오 개발자 콘솔 **네이티브 앱 키** (REST API 키와 다름).
  /// Android `strings.xml`의 `kakao_native_app_key`와 동일해야 합니다.
  static String? get kakaoNativeAppKey {
    const fromDefine = String.fromEnvironment(
      'KAKAO_NATIVE_APP_KEY',
      defaultValue: '',
    );
    if (fromDefine.isNotEmpty) return fromDefine.trim();
    if (dotenv.isInitialized) {
      final fromFile = dotenv.env['KAKAO_NATIVE_APP_KEY']?.trim();
      if (fromFile != null && fromFile.isNotEmpty) return fromFile;
    }
    return null;
  }

  static String? get naverClientId {
    const fromDefine = String.fromEnvironment(
      'NAVER_CLIENT_ID',
      defaultValue: '',
    );
    if (fromDefine.isNotEmpty) return fromDefine.trim();
    if (dotenv.isInitialized) {
      final fromFile = dotenv.env['NAVER_CLIENT_ID']?.trim();
      if (fromFile != null && fromFile.isNotEmpty) return fromFile;
    }
    return null;
  }

  static String? get naverClientSecret {
    const fromDefine = String.fromEnvironment(
      'NAVER_CLIENT_SECRET',
      defaultValue: '',
    );
    if (fromDefine.isNotEmpty) return fromDefine.trim();
    if (dotenv.isInitialized) {
      final fromFile = dotenv.env['NAVER_CLIENT_SECRET']?.trim();
      if (fromFile != null && fromFile.isNotEmpty) return fromFile;
    }
    return null;
  }

  static String get naverClientName {
    const fromDefine = String.fromEnvironment(
      'NAVER_CLIENT_NAME',
      defaultValue: '',
    );
    if (fromDefine.isNotEmpty) return fromDefine.trim();
    if (dotenv.isInitialized) {
      final fromFile = dotenv.env['NAVER_CLIENT_NAME']?.trim();
      if (fromFile != null && fromFile.isNotEmpty) return fromFile;
    }
    return '청년 인사이트';
  }

  static String _normalizeUrl(String value) {
    var url = value.trim();
    while (url.endsWith('/')) {
      url = url.substring(0, url.length - 1);
    }
    return url;
  }
}
