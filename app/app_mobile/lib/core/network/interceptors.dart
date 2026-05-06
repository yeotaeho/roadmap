import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';

class AuthInterceptor extends Interceptor {
  AuthInterceptor({
    required this.dio,
    required this.baseUrl,
    required this.getAccessToken,
    required this.getRefreshToken,
    required this.saveTokens,
    required this.clearSession,
  });

  final Dio dio;
  final String baseUrl;
  final Future<String?> Function() getAccessToken;
  final Future<String?> Function() getRefreshToken;
  final Future<void> Function(String accessToken, String? refreshToken) saveTokens;
  final Future<void> Function() clearSession;
  bool _isRefreshing = false;

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
  Future<void> onError(
    DioException err,
    ErrorInterceptorHandler handler,
  ) async {
    if (kDebugMode) {
      debugPrint('[Dio] ${err.requestOptions.uri} → ${err.message}');
    }
    final statusCode = err.response?.statusCode;
    final request = err.requestOptions;
    final isRefreshRequest = request.path.contains('/api/oauth/refresh');
    final alreadyRetried = request.extra['retried'] == true;

    if (statusCode != 401 || isRefreshRequest || alreadyRetried || _isRefreshing) {
      handler.next(err);
      return;
    }

    _isRefreshing = true;
    try {
      final refreshToken = await getRefreshToken();
      if (refreshToken == null || refreshToken.isEmpty) {
        await clearSession();
        handler.next(err);
        return;
      }

      final refreshDio = Dio(
        BaseOptions(
          baseUrl: baseUrl,
          connectTimeout: const Duration(seconds: 15),
          receiveTimeout: const Duration(seconds: 30),
          headers: {'Accept': 'application/json'},
        ),
      );
      final refreshRes = await refreshDio.post<Map<String, dynamic>>(
        '/api/oauth/refresh',
        queryParameters: {'client': 'mobile'},
        data: {'refreshToken': refreshToken},
      );

      final body = refreshRes.data ?? const <String, dynamic>{};
      final newAccess = body['accessToken']?.toString();
      final newRefresh = body['refreshToken']?.toString();
      if (newAccess == null || newAccess.isEmpty) {
        await clearSession();
        handler.next(err);
        return;
      }

      await saveTokens(newAccess, newRefresh);

      request.headers['Authorization'] = 'Bearer $newAccess';
      request.extra['retried'] = true;
      final retried = await dio.fetch<dynamic>(request);
      handler.resolve(retried);
      return;
    } catch (_) {
      await clearSession();
      handler.next(err);
      return;
    } finally {
      _isRefreshing = false;
    }
  }
}
