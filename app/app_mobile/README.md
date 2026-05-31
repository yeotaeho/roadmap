# app_mobile

청년 인사이트 Flutter 모바일 앱.

## 환경 설정 (SSOT: `dart_defines/local.env`)

1. `dart_defines/example.env` 를 복사해 `dart_defines/local.env` 를 만들고 값을 채웁니다.
2. **필수 키**
   - `API_BASE_URL` — `adb reverse` 사용 시 `http://localhost:8000`
   - `GOOGLE_SERVER_CLIENT_ID` — Google Cloud **Web** OAuth Client ID
   - `KAKAO_NATIVE_APP_KEY`, `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`, `NAVER_CLIENT_NAME`

### env가 앱에 들어가는 방식

| 방식 | 설명 |
|------|------|
| **Asset 번들** (기본) | `flutter run` / `flutter build` 시 `local.env` 가 APK에 포함 → `AppEnv.load()` |
| `--dart-define-from-file` (선택) | compile-time 주입, IDE settings/launch.json 에서 자동 적용 |
| Android Gradle | 카카오/네이버 네이티브 SDK string 리소스 |

> **env 변경 후** `flutter clean` 후 full rebuild 필요 (hot reload 불가).

## 실행

### 일반 CLI (권장)

```powershell
cd app/app_mobile
flutter run -d emulator-5554
```

`local.env` 가 있으면 빌드 시 asset 으로 포함되어 Google 로그인 등에 사용됩니다.

### adb reverse + dev 스크립트

PC `localhost:8000` 백엔드에 붙을 때:

```powershell
.\scripts\dev.ps1 -Device emulator-5554
```

### VS Code / Cursor

- 터미널 `flutter run`: asset 방식으로 동작
- Run and Debug `app_mobile (debug)`: dart-define 추가 주입

### APK 빌드

```powershell
.\scripts\build.ps1
```

### local.env 없을 때

```powershell
Copy-Item dart_defines/example.env dart_defines/local.env
# 값 채운 뒤 빌드
```
