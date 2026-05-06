import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../auth/auth_service.dart';
import '../auth/token_storage.dart';
import '../config/app_env.dart';
import '../network/dio_client.dart';

final tokenStorageProvider = Provider<TokenStorage>((ref) {
  return TokenStorage();
});

/// FastAPI 호출용 Dio. 요청마다 [TokenStorage.readAccessToken]으로 헤더 갱신.
final dioProvider = Provider<Dio>((ref) {
  final storage = ref.watch(tokenStorageProvider);
  return DioClient.create(
    baseUrl: AppEnv.apiBaseUrl,
    tokenStorage: storage,
  );
});

final authServiceProvider = Provider<AuthService>((ref) {
  final storage = ref.watch(tokenStorageProvider);
  return AuthService(storage: storage);
});
