# app_mobile

청년 인사이트 Flutter 모바일 앱.

## 환경 설정

1. `dart_defines/example.env` 를 복사해 `dart_defines/local.env` 를 만들고 값을 채웁니다.
   - `KAKAO_NATIVE_APP_KEY`, `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`, `NAVER_CLIENT_NAME`
   - `API_BASE_URL` (기본: `http://localhost:8000` — `adb reverse` 와 함께 사용)
2. `local.env` 의 카카오/네이버 키는 Gradle 빌드시 안드로이드 string 리소스로 자동 주입됩니다.

## 실행 (Windows / PowerShell)

`scripts/dev.ps1` 한 번으로 다음을 자동 처리합니다.

- 연결된 디바이스 감지 (1개면 자동 선택, 2개 이상이면 선택 메뉴)
- 해당 디바이스에 `adb reverse tcp:8000 tcp:8000` 적용 (PC 백엔드를 폰의 `localhost:8000` 으로 노출)
- `flutter run -d <device> --dart-define-from-file=dart_defines/local.env`

```powershell
# 기본 실행
.\scripts\dev.ps1

# 특정 디바이스 지정
.\scripts\dev.ps1 -Device emulator-5554

# 다른 포트 추가
.\scripts\dev.ps1 -Port 8000,8080

# release 빌드
.\scripts\dev.ps1 -Release

# flutter run 에 추가 인자 전달
.\scripts\dev.ps1 -- --verbose
```

> 처음 실행 시 PowerShell 실행 정책 때문에 막히면:
> ```powershell
> Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
> ```

### `adb reverse` 만 따로 적용하고 싶을 때

이미 다른 방식으로 `flutter run` 을 띄우고 있다면:

```powershell
.\scripts\adb-reverse.ps1                 # 모든 디바이스, 8000 포트
.\scripts\adb-reverse.ps1 -Port 8000,8080 # 여러 포트
.\scripts\adb-reverse.ps1 -Device RF9NC03G9VL
```

> `adb reverse` 는 USB 분리/재부팅/에뮬레이터 재기동 시 사라지므로 그때마다 다시 실행해야 합니다.
