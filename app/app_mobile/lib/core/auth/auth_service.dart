import 'package:dio/dio.dart';
import 'package:flutter_naver_login/flutter_naver_login.dart';
import 'package:flutter_naver_login/interface/types/naver_login_status.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:kakao_flutter_sdk/kakao_flutter_sdk.dart';

import '../config/app_env.dart';
import 'token_storage.dart';

class AuthService {
  AuthService({
    required TokenStorage storage,
    Dio? dio,
  })  : _storage = storage,
        _dio = dio ??
            Dio(
              BaseOptions(
                baseUrl: AppEnv.apiBaseUrl,
                connectTimeout: const Duration(seconds: 15),
                receiveTimeout: const Duration(seconds: 30),
                headers: {'Accept': 'application/json'},
              ),
            );

  final TokenStorage _storage;
  final Dio _dio;

  Future<bool> hasSession() async {
    final access = await _storage.readAccessToken();
    final refresh = await _storage.readRefreshToken();
    return (access?.isNotEmpty ?? false) || (refresh?.isNotEmpty ?? false);
  }

  Future<bool> restoreSessionIfPossible() async {
    final access = await _storage.readAccessToken();
    if (access != null && access.isNotEmpty) {
      try {
        await _dio.get(
          '/api/oauth/me',
          options: Options(headers: {'Authorization': 'Bearer $access'}),
        );
        return true;
      } on DioException catch (e) {
        if (e.response?.statusCode != 401) rethrow;
      }
    }
    return refreshAccessToken();
  }

  Future<void> loginWithGoogleNative() async {
    final googleSignIn = GoogleSignIn(
      scopes: const <String>['email', 'profile'],
      serverClientId: AppEnv.googleServerClientId,
    );
    await googleSignIn.signOut();
    final account = await googleSignIn.signIn();
    if (account == null) {
      throw Exception('사용자가 구글 로그인을 취소했습니다.');
    }
    final auth = await account.authentication;
    final idToken = auth.idToken;
    if (idToken == null || idToken.isEmpty) {
      throw Exception('Google idToken을 가져오지 못했습니다.');
    }

    final tokenResponse = await _dio.post<Map<String, dynamic>>(
      '/api/oauth/google/native-login',
      queryParameters: {'client': 'mobile'},
      data: {
        'idToken': idToken,
        'deviceId': 'android-emulator',
        'deviceName': 'flutter-app',
      },
    );
    await _persistTokens(tokenResponse.data);
  }

  Future<void> loginWithKakaoNative() async {
    final key = AppEnv.kakaoNativeAppKey;
    if (key == null || key.isEmpty) {
      throw Exception(
        '카카오 네이티브 앱 키가 없습니다. KAKAO_NATIVE_APP_KEY를 설정하세요.',
      );
    }

    OAuthToken token;
    if (await isKakaoTalkInstalled()) {
      try {
        token = await UserApi.instance.loginWithKakaoTalk();
      } catch (_) {
        token = await UserApi.instance.loginWithKakaoAccount();
      }
    } else {
      token = await UserApi.instance.loginWithKakaoAccount();
    }

    final access = token.accessToken;
    if (access.isEmpty) {
      throw Exception('카카오 액세스 토큰을 받지 못했습니다.');
    }

    final tokenResponse = await _dio.post<Map<String, dynamic>>(
      '/api/oauth/kakao/native-login',
      queryParameters: {'client': 'mobile'},
      data: {
        'accessToken': access,
        'deviceId': 'flutter-app',
        'deviceName': 'flutter-app',
      },
    );
    await _persistTokens(tokenResponse.data);
  }

  Future<void> loginWithNaverNative() async {
    final id = AppEnv.naverClientId;
    final secret = AppEnv.naverClientSecret;
    if (id == null ||
        id.isEmpty ||
        secret == null ||
        secret.isEmpty) {
      throw Exception(
        '네이버 클라이언트 설정이 없습니다. NAVER_CLIENT_ID / NAVER_CLIENT_SECRET과 '
        'Android strings.xml(meta-data)를 확인하세요.',
      );
    }

    final result = await FlutterNaverLogin.logIn();
    if (result.status != NaverLoginStatus.loggedIn) {
      throw Exception(
        result.errorMessage ?? '네이버 로그인에 실패했습니다.',
      );
    }
    final naverToken = result.accessToken;
    final access = naverToken?.accessToken;
    if (access == null || access.isEmpty) {
      throw Exception('네이버 액세스 토큰을 받지 못했습니다.');
    }

    final tokenResponse = await _dio.post<Map<String, dynamic>>(
      '/api/oauth/naver/native-login',
      queryParameters: {'client': 'mobile'},
      data: {
        'accessToken': access,
        'deviceId': 'flutter-app',
        'deviceName': 'flutter-app',
      },
    );
    await _persistTokens(tokenResponse.data);
  }

  Future<void> loginWithProvider(String provider) async {
    switch (provider) {
      case 'google':
        await loginWithGoogleNative();
      case 'kakao':
        await loginWithKakaoNative();
      case 'naver':
        await loginWithNaverNative();
      default:
        throw Exception('지원하지 않는 로그인 제공자입니다.');
    }
  }

  Future<bool> refreshAccessToken() async {
    final refresh = await _storage.readRefreshToken();
    if (refresh == null || refresh.isEmpty) return false;

    try {
      final response = await _dio.post<Map<String, dynamic>>(
        '/api/oauth/refresh',
        queryParameters: {'client': 'mobile'},
        data: {'refreshToken': refresh},
      );
      await _persistTokens(response.data);
      return true;
    } on DioException {
      await _storage.clearSession();
      return false;
    }
  }

  Future<void> logout() async {
    try {
      final refresh = await _storage.readRefreshToken();
      final access = await _storage.readAccessToken();
      await _dio.post(
        '/api/oauth/logout',
        options: Options(
          headers: {
            if (refresh != null && refresh.isNotEmpty) 'Cookie': 'refreshToken=$refresh',
            if (access != null && access.isNotEmpty) 'Authorization': 'Bearer $access',
          },
        ),
      );
    } catch (_) {
      // 클라이언트 세션 정리가 우선이므로 서버 실패는 무시.
    } finally {
      await _storage.clearSession();
    }
  }

  Future<void> _persistTokens(Map<String, dynamic>? payload) async {
    if (payload == null) {
      throw Exception('토큰 응답이 비어 있습니다.');
    }
    final accessToken = payload['accessToken']?.toString();
    final refreshToken = payload['refreshToken']?.toString();
    if (accessToken == null || accessToken.isEmpty) {
      throw Exception('Access Token이 응답에 없습니다.');
    }
    await _storage.writeAccessToken(accessToken);
    if (refreshToken != null && refreshToken.isNotEmpty) {
      await _storage.writeRefreshToken(refreshToken);
    }
  }
}
