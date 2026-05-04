import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';

import 'interceptors.dart';

abstract final class DioClient {
  /// [getAccessToken]은 요청마다 호출되므로, 로그인 후 저장소에만 쓰면 이후 API에 자동 반영됩니다.
  static Dio create({
    required Future<String?> Function() getAccessToken,
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
    dio.interceptors.add(AuthInterceptor(getAccessToken: getAccessToken));
    if (kDebugMode) {
      dio.interceptors.add(LogInterceptor(requestBody: true, responseBody: true));
    }
    return dio;
  }
}
