import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// 액세스·리프레시 토큰 보관. 로그인 플로우 구현 시 [writeAccessToken] 등을 호출하면
/// [Dio] `AuthInterceptor`가 이후 요청에 `Authorization` 헤더를 붙입니다.
class TokenStorage {
  TokenStorage([FlutterSecureStorage? storage])
      : _storage = storage ?? const FlutterSecureStorage();

  final FlutterSecureStorage _storage;

  static const _keyAccess = 'access_token';
  static const _keyRefresh = 'refresh_token';

  Future<String?> readAccessToken() => _storage.read(key: _keyAccess);

  Future<void> writeAccessToken(String value) =>
      _storage.write(key: _keyAccess, value: value);

  Future<String?> readRefreshToken() => _storage.read(key: _keyRefresh);

  Future<void> writeRefreshToken(String value) =>
      _storage.write(key: _keyRefresh, value: value);

  Future<void> clearSession() async {
    await _storage.delete(key: _keyAccess);
    await _storage.delete(key: _keyRefresh);
  }
}
