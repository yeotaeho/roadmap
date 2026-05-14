import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
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

  /// 현재 로그인 사용자의 기본 프로필 조회 (`GET /api/oauth/me`).
  /// 401/그 외 오류는 `null` 로 반환하여 호출 측이 단순 분기로 처리할 수 있게 한다.
  Future<UserInfo?> getMe() async {
    final access = await _storage.readAccessToken();
    if (access == null || access.isEmpty) return null;
    try {
      final res = await _dio.get<Map<String, dynamic>>(
        '/api/oauth/me',
        options: Options(headers: {'Authorization': 'Bearer $access'}),
      );
      return UserInfo.fromJson(res.data);
    } on DioException {
      return null;
    }
  }

  /// 닉네임/프로필 이미지 업데이트. 서버 라우트는 `PUT /api/oauth/me`.
  /// 빈 값(null)은 서버에 전송하지 않는다 → `name`/`profileImage` 둘 중 하나만 변경 가능.
  Future<UserInfo> updateMe({
    String? name,
    String? profileImage,
  }) async {
    final access = await _storage.readAccessToken();
    if (access == null || access.isEmpty) {
      throw Exception('로그인 세션이 없습니다.');
    }
    final body = <String, dynamic>{
      'name': ?name,
      'profileImage': ?profileImage,
    };
    if (body.isEmpty) {
      throw ArgumentError('업데이트할 필드가 없습니다.');
    }
    final res = await _dio.put<Map<String, dynamic>>(
      '/api/oauth/me',
      options: Options(headers: {'Authorization': 'Bearer $access'}),
      data: body,
    );
    final user = UserInfo.fromJson(res.data);
    if (user == null) {
      throw Exception('사용자 응답이 비어 있습니다.');
    }
    return user;
  }

  /// 현재 로그인 사용자의 sync-profile 조회.
  /// 서버는 프로필이 없어도 `{userId, targetJob: null, interestKeywords: []}` 형태로 응답한다.
  Future<SyncProfile?> getSyncProfile() async {
    final access = await _storage.readAccessToken();
    if (access == null || access.isEmpty) return null;
    try {
      final res = await _dio.get<Map<String, dynamic>>(
        '/api/user/sync-profile',
        options: Options(headers: {'Authorization': 'Bearer $access'}),
      );
      return SyncProfile.fromJson(res.data);
    } on DioException {
      return null;
    }
  }

  /// 회원가입 보충 정보가 채워졌는지 확인 (목표 직무 + 관심 키워드 1개 이상).
  Future<bool> isProfileComplete() async {
    final profile = await getSyncProfile();
    if (profile == null) return false;
    final job = profile.targetJob?.trim() ?? '';
    return job.isNotEmpty && profile.interestKeywords.isNotEmpty;
  }

  /// sync-profile upsert. 서버 라우트는 `PUT /api/user/sync-profile`.
  Future<SyncProfile> upsertSyncProfile({
    required String? targetJob,
    required List<String> interestKeywords,
  }) async {
    final access = await _storage.readAccessToken();
    if (access == null || access.isEmpty) {
      throw Exception('로그인 세션이 없습니다.');
    }
    final res = await _dio.put<Map<String, dynamic>>(
      '/api/user/sync-profile',
      options: Options(headers: {'Authorization': 'Bearer $access'}),
      data: {
        'targetJob': targetJob,
        'interestKeywords': interestKeywords,
      },
    );
    final profile = SyncProfile.fromJson(res.data);
    if (profile == null) {
      throw Exception('프로필 응답이 비어 있습니다.');
    }
    return profile;
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
    debugPrint(
      '[Naver] status=${result.status} '
      'errorMessage=${result.errorMessage} '
      'hasAccessToken=${(result.accessToken?.accessToken ?? '').isNotEmpty}',
    );
    if (result.status != NaverLoginStatus.loggedIn) {
      throw Exception(
        '네이버 로그인 실패 (status=${result.status}): '
        '${result.errorMessage ?? '알 수 없는 오류'}',
      );
    }

    // logIn() 응답에 토큰이 비어 오는 케이스(특히 네이버 앱 경유 로그인 직후
    // 토큰 교환이 완료되기 전 반환되는 경우)를 위해 getCurrentAccessToken 으로 한 번 더 조회.
    String? access = result.accessToken?.accessToken;
    if (access == null || access.isEmpty) {
      for (var i = 0; i < 5; i++) {
        await Future<void>.delayed(const Duration(milliseconds: 300));
        final fresh = await FlutterNaverLogin.getCurrentAccessToken();
        debugPrint(
          '[Naver] retry($i) hasAccessToken=${fresh.accessToken.isNotEmpty}',
        );
        if (fresh.accessToken.isNotEmpty) {
          access = fresh.accessToken;
          break;
        }
      }
    }
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

/// `GET /api/oauth/me` 응답을 표현. 서버 키 이름 그대로(camelCase) 매핑.
class UserInfo {
  const UserInfo({
    required this.id,
    this.name,
    this.email,
    this.nickname,
    this.profileImage,
    this.provider = '',
  });

  final String id;
  final String? name;
  final String? email;
  final String? nickname;
  final String? profileImage;
  final String provider;

  /// 표시용 이름 우선순위: nickname → name → email 앞부분 → '회원'
  String get displayName {
    final n = (nickname?.trim().isNotEmpty ?? false) ? nickname!.trim() : null;
    if (n != null) return n;
    final nm = (name?.trim().isNotEmpty ?? false) ? name!.trim() : null;
    if (nm != null) return nm;
    final e = email;
    if (e != null && e.contains('@')) return e.split('@').first;
    return '회원';
  }

  static UserInfo? fromJson(Map<String, dynamic>? json) {
    if (json == null) return null;
    final id = json['id']?.toString();
    if (id == null || id.isEmpty) return null;
    String? str(String key) {
      final v = json[key];
      if (v == null) return null;
      final s = v.toString().trim();
      return s.isEmpty ? null : s;
    }

    return UserInfo(
      id: id,
      name: str('name'),
      email: str('email'),
      nickname: str('nickname'),
      profileImage: str('profileImage'),
      provider: str('provider') ?? '',
    );
  }
}

/// `GET /api/user/sync-profile` 응답을 표현.
class SyncProfile {
  const SyncProfile({
    required this.userId,
    this.targetJob,
    this.interestKeywords = const <String>[],
  });

  final String userId;
  final String? targetJob;
  final List<String> interestKeywords;

  static SyncProfile? fromJson(Map<String, dynamic>? json) {
    if (json == null) return null;
    final raw = json['interestKeywords'];
    final keywords = raw is List
        ? raw.map((e) => e.toString()).where((s) => s.isNotEmpty).toList()
        : <String>[];
    return SyncProfile(
      userId: json['userId']?.toString() ?? '',
      targetJob: (json['targetJob'] as String?)?.trim().isNotEmpty == true
          ? (json['targetJob'] as String).trim()
          : null,
      interestKeywords: keywords,
    );
  }
}
