import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';

import '../auth/token_storage.dart';
import 'interceptors.dart';

abstract final class DioClient {
  /// [getAccessToken]은 요청마다 호출되므로, 로그인 후 저장소에만 쓰면 이후 API에 자동 반영됩니다.
  static Dio create({
    required TokenStorage tokenStorage,
    required String baseUrl,
  }) {
    final dio = Dio(
      BaseOptions(
        baseUrl: baseUrl,
        connectTimeout: const Duration(seconds: 15),
        receiveTimeout: const Duration(seconds: 30),
        headers: {'Accept': 'application/json'},
      ),
    );
    dio.interceptors.add(
      AuthInterceptor(
        dio: dio,
        baseUrl: baseUrl,
        getAccessToken: tokenStorage.readAccessToken,
        getRefreshToken: tokenStorage.readRefreshToken,
        saveTokens: (accessToken, refreshToken) async {
          await tokenStorage.writeAccessToken(accessToken);
          if (refreshToken != null && refreshToken.isNotEmpty) {
            await tokenStorage.writeRefreshToken(refreshToken);
          }
        },
        clearSession: tokenStorage.clearSession,
      ),
    );
    if (kDebugMode) {
      dio.interceptors.add(LogInterceptor(requestBody: true, responseBody: true));
    }
    return dio;
  }
}
