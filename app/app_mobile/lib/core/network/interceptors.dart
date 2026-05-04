import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';

/// JWT 첨부. 401 시 리프레시는 추후 [TokenStorage]·백엔드 계약에 맞게 [onError]에서 확장.
class AuthInterceptor extends Interceptor {
  AuthInterceptor({required this.getAccessToken});

  final Future<String?> Function() getAccessToken;

  @override
  void onRequest(
    RequestOptions options,
    RequestInterceptorHandler handler,
  ) async {
    final token = await getAccessToken();
    if (token != null && token.isNotEmpty) {
      options.headers['Authorization'] = 'Bearer $token';
    }
    handler.next(options);
  }

  @override
  void onError(DioException err, ErrorInterceptorHandler handler) {
    if (kDebugMode) {
      debugPrint('[Dio] ${err.requestOptions.uri} → ${err.message}');
    }
    handler.next(err);
  }
}
