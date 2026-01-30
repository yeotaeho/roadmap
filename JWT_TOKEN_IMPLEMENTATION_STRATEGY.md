# JWT 토큰 발급 구현 전략

이 문서는 백엔드 서버와 프론트엔드 클라이언트에서 실제 JWT 토큰을 발급받고 사용하는 전략을 설명합니다.  
카카오, 구글, 네이버 세 가지 OAuth 제공자에 대해 동일한 방식으로 구현합니다.

---

## 백엔드 서버 (OAuth-Service) 구현 전략

### 1. OAuth API 통신 ✅ (현재 구현됨)

#### 1.1 카카오 API 통신 ✅
- **필요한 구현 로직**: HTTP 클라이언트 구현
- **설명**: 
  - 인가 코드를 카카오 API 서버에 전송하여 액세스 토큰을 받는 로직
  - 받은 액세스 토큰으로 사용자 정보를 요청하는 로직
- **현재 상태**: `KakaoOAuthService`에서 이미 구현되어 있음
- **구현 위치**: `service/oauth/src/main/java/kr/yeotaeho/api/service/KakaoOAuthService.java`

#### 1.2 구글 API 통신 ✅
- **필요한 구현 로직**: HTTP 클라이언트 구현
- **설명**: 
  - 인가 코드를 구글 API 서버에 전송하여 액세스 토큰을 받는 로직
  - 받은 액세스 토큰으로 사용자 정보를 요청하는 로직
- **현재 상태**: `GoogleOAuthService`에서 이미 구현되어 있음
- **구현 위치**: `service/oauth/src/main/java/kr/yeotaeho/api/service/GoogleOAuthService.java`

#### 1.3 네이버 API 통신 ✅
- **필요한 구현 로직**: HTTP 클라이언트 구현
- **설명**: 
  - 인가 코드와 state를 네이버 API 서버에 전송하여 액세스 토큰을 받는 로직
  - 받은 액세스 토큰으로 사용자 정보를 요청하는 로직
- **현재 상태**: `NaverOAuthService`에서 이미 구현되어 있음
- **구현 위치**: `service/oauth/src/main/java/kr/yeotaeho/api/service/NaverOAuthService.java`

### 2. 사용자 식별/등록 ❌ (추가 필요)
- **필요한 구현 로직**: DB 연동 및 비즈니스 로직
- **설명**: 
  - OAuth 제공자로부터 받은 고유 ID를 DB에서 조회
  - 기존 회원인 경우: 로그인 처리
  - 신규 회원인 경우: 사용자 정보 저장 (회원가입 처리)
- **구현 위치**: 
  - `KakaoController.kakaoCallback()` 메서드 내부
  - `GoogleController.googleCallback()` 메서드 내부
  - `NaverController.naverCallback()` 메서드 내부
- **필요한 작업**:
  - User 엔티티/모델 정의 (OAuth 제공자 정보 포함)
  - UserRepository 생성
  - 사용자 조회/저장 로직 구현 (공통 서비스로 추출 권장)
  - OAuth 제공자별 고유 ID 매핑 (kakaoId, googleId, naverId)

### 3. JWT 생성 ❌ (추가 필요)
- **필요한 구현 로직**: JWT 라이브러리 사용 및 구현
- **설명**: 
  - 서버의 **Secret Key**로 서명된 JWT 생성
  - 언어별 라이브러리 사용:
    - Java: Spring Security JWT, jjwt 등
    - Node.js: jsonwebtoken
    - Python: PyJWT
  - 토큰에 포함할 정보:
    - 사용자 ID (userId) - 내부 DB의 사용자 ID
    - OAuth 제공자 정보 (provider: "kakao" | "google" | "naver")
    - 권한 (role/permissions)
    - 만료 시간 (expiration time)
    - 기타 필요한 클레임
- **구현 위치**: 
  - 공통 JWT 유틸리티 클래스 생성 (모든 OAuth 제공자에서 공통 사용)
  - `KakaoController.kakaoCallback()` 메서드 내부
  - `GoogleController.googleCallback()` 메서드 내부
  - `NaverController.naverCallback()` 메서드 내부
- **필요한 작업**:
  - JWT 라이브러리 의존성 추가 (build.gradle)
  - JWT 유틸리티 클래스 생성 (예: `JwtTokenUtil.java`)
  - Secret Key 설정 (application.yaml 또는 환경 변수)
  - JWT 생성 로직 구현 (공통 메서드로 추출)

### 4. 응답 ⚠️ (수정 필요)
- **필요한 구현 로직**: JWT 반환
- **설명**: 
  - 생성된 JWT를 HTTP 응답 body 또는 header로 프론트엔드에 전달
- **현재 상태**: 
  - 카카오: 더미 토큰 반환 중 (`"jwt-token-" + System.currentTimeMillis()`)
  - 구글: 더미 토큰 반환 중 (`"jwt-token-" + System.currentTimeMillis()`)
  - 네이버: 더미 토큰 반환 중 (`"jwt-token-" + System.currentTimeMillis()`)
- **수정 필요**: 세 개의 컨트롤러 모두 실제 생성된 JWT로 교체

### 5. API 인증 미들웨어 ❌ (추가 필요)
- **필요한 구현 로직**: 토큰 검증 로직
- **설명**: 
  - 로그인 후 사용자가 보호된 API를 요청할 때 (예: `/mypage`, `/posts`)
  - HTTP header에서 JWT를 추출
  - 서명 검증 및 만료 시간 확인을 통해 유효한 사용자인지 검증하는 미들웨어/필터 로직 구현
- **구현 위치**: Spring Security Filter 또는 Interceptor
- **필요한 작업**:
  - JWT 검증 필터 생성
  - Spring Security 설정에 필터 등록
  - 보호된 엔드포인트에 인증 요구 설정

---

## 프론트엔드 (클라이언트) 구현 전략

### 1. 인가 코드 추출 ✅ (현재 구현됨)

#### 1.1 카카오 인가 코드 추출 ✅
- **필요한 구현 로직**: URL 파싱 로직
- **설명**: 
  - 카카오에서 리다이렉트된 URL에서 `code=` 파라미터에 담긴 인가 코드를 추출하는 로직
- **현재 상태**: `auth/kakao/callback/page.tsx`에서 `searchParams.get('code')`로 구현됨

#### 1.2 구글 인가 코드 추출 ✅
- **필요한 구현 로직**: URL 파싱 로직
- **설명**: 
  - 구글에서 리다이렉트된 URL에서 `code=` 파라미터에 담긴 인가 코드를 추출하는 로직
- **현재 상태**: `auth/google/callback/page.tsx`에서 `searchParams.get('code')`로 구현됨

#### 1.3 네이버 인가 코드 추출 ✅
- **필요한 구현 로직**: URL 파싱 로직
- **설명**: 
  - 네이버에서 리다이렉트된 URL에서 `code=` 및 `state=` 파라미터에 담긴 인가 코드를 추출하는 로직
- **현재 상태**: `auth/naver/callback/page.tsx`에서 `searchParams.get('code')`, `searchParams.get('state')`로 구현됨

### 2. 콜백 요청 ✅ (현재 구현됨)

#### 2.1 카카오 콜백 요청 ✅
- **필요한 구현 로직**: 백엔드 API 호출
- **설명**: 
  - 추출한 인가 코드를 백엔드의 콜백 엔드포인트 (`POST /api/oauth/kakao/callback`)로 전송하는 로직
- **현재 상태**: `auth/kakao/callback/page.tsx`에서 `fetch` API로 구현됨

#### 2.2 구글 콜백 요청 ✅
- **필요한 구현 로직**: 백엔드 API 호출
- **설명**: 
  - 추출한 인가 코드를 백엔드의 콜백 엔드포인트 (`POST /api/oauth/google/callback`)로 전송하는 로직
- **현재 상태**: `auth/google/callback/page.tsx`에서 `fetch` API로 구현됨

#### 2.3 네이버 콜백 요청 ✅
- **필요한 구현 로직**: 백엔드 API 호출
- **설명**: 
  - 추출한 인가 코드와 state를 백엔드의 콜백 엔드포인트 (`POST /api/oauth/naver/callback`)로 전송하는 로직
- **현재 상태**: `auth/naver/callback/page.tsx`에서 `fetch` API로 구현됨

### 3. 토큰 저장 ❌ (추가 필요)
- **필요한 구현 로직**: JWT 저장 로직
- **설명**: 
  - 백엔드로부터 받은 JWT를 **안전한 위치**에 저장하는 로직
  - 저장 위치 옵션:
    - **HTTP Only Cookie** (권장): XSS 공격 방지
    - **localStorage**: 브라우저 재시작 후에도 유지
    - **sessionStorage**: 탭 종료 시 삭제
- **현재 상태**: 세 개의 콜백 페이지 모두 TODO 주석만 있고 실제 저장 로직 없음
- **구현 위치**: 
  - `auth/kakao/callback/page.tsx`의 `handleCallback` 함수 내부
  - `auth/google/callback/page.tsx`의 `handleCallback` 함수 내부
  - `auth/naver/callback/page.tsx`의 `handleCallback` 함수 내부
- **필요한 작업**:
  - 공통 토큰 저장 유틸리티 함수 생성 (권장)
  - 세 개의 콜백 페이지에서 공통 함수 호출
  ```typescript
  // 예시 코드 (공통 유틸리티)
  // utils/tokenStorage.ts
  export const saveToken = (accessToken: string) => {
      localStorage.setItem('accessToken', accessToken);
      // 또는 HTTP Only Cookie로 저장 (백엔드에서 Set-Cookie 헤더로 설정)
  };
  
  // 각 콜백 페이지에서 사용
  if (response.ok) {
      const data = await response.json();
      saveToken(data.accessToken);
  }
  ```

### 4. API 요청 시 사용 ❌ (추가 필요)
- **필요한 구현 로직**: HTTP 헤더 포함
- **설명**: 
  - 보호된 API 요청 시, 저장된 JWT를 꺼내 `Authorization: Bearer <JWT>` 형태로 HTTP 요청 헤더에 포함하여 보내는 로직
- **구현 방법**:
  - **Axios Interceptor 사용** (권장)
  - **Fetch API 래퍼 함수 생성**
  - **각 API 호출마다 수동으로 헤더 추가**
- **필요한 작업**:
  ```typescript
  // 예시: Axios Interceptor
  axios.interceptors.request.use((config) => {
      const token = localStorage.getItem('accessToken');
      if (token) {
          config.headers.Authorization = `Bearer ${token}`;
      }
      return config;
  });
  ```

---

## 구현 우선순위

### Phase 1: 백엔드 JWT 생성 (필수)
1. JWT 라이브러리 의존성 추가 (build.gradle)
2. JWT 유틸리티 클래스 생성 (`JwtTokenUtil.java`)
3. Secret Key 설정 (application.yaml 또는 환경 변수)
4. JWT 생성 로직 구현 (공통 메서드)
5. 세 개의 컨트롤러에서 더미 토큰을 실제 JWT로 교체
   - `KakaoController.kakaoCallback()`
   - `GoogleController.googleCallback()`
   - `NaverController.naverCallback()`

### Phase 2: 사용자 관리 (필수)
1. User 엔티티/모델 정의 (OAuth 제공자 정보 포함)
2. UserRepository 생성
3. 사용자 조회/저장 로직 구현 (공통 서비스로 추출)
4. JWT에 사용자 정보 포함 (userId, provider 등)

### Phase 3: 프론트엔드 토큰 저장 (필수)
1. 공통 토큰 저장 유틸리티 함수 생성 (`utils/tokenStorage.ts`)
2. 세 개의 콜백 페이지에서 JWT 저장 로직 추가
   - `auth/kakao/callback/page.tsx`
   - `auth/google/callback/page.tsx`
   - `auth/naver/callback/page.tsx`
3. 토큰 저장 위치 결정 (localStorage/Cookie)

### Phase 4: API 인증 (필수)
1. 백엔드: JWT 검증 미들웨어 구현
2. 프론트엔드: API 요청 시 JWT 헤더 포함 로직 구현 (Axios Interceptor 또는 Fetch 래퍼)

### Phase 5: 보안 강화 (권장)
1. Refresh Token 구현
2. 토큰 만료 시 자동 갱신 로직
3. 로그아웃 시 토큰 삭제

---

## 현재 상태 요약

### ✅ 구현 완료
- **카카오 OAuth**
  - 카카오 API 통신 (백엔드)
  - 인가 코드 추출 (프론트엔드)
  - 콜백 요청 (프론트엔드)
- **구글 OAuth**
  - 구글 API 통신 (백엔드)
  - 인가 코드 추출 (프론트엔드)
  - 콜백 요청 (프론트엔드)
- **네이버 OAuth**
  - 네이버 API 통신 (백엔드)
  - 인가 코드 및 state 추출 (프론트엔드)
  - 콜백 요청 (프론트엔드)

### ❌ 미구현 (세 개의 OAuth 제공자 공통)
- 사용자 DB 조회/등록 (백엔드)
- JWT 생성 (백엔드)
- 실제 JWT 반환 (백엔드 - 현재 더미 토큰)
- JWT 저장 (프론트엔드)
- API 요청 시 JWT 헤더 포함 (프론트엔드)
- JWT 검증 미들웨어 (백엔드)

---

## 참고사항

### 공통 사항
- JWT Secret Key는 반드시 환경 변수로 관리하고, 절대 코드에 하드코딩하지 마세요.
- HTTP Only Cookie를 사용하면 XSS 공격을 방지할 수 있지만, CSRF 공격에 대한 대비도 필요합니다.
- JWT 만료 시간은 보안과 사용자 경험의 균형을 고려하여 설정하세요 (일반적으로 Access Token: 15분~1시간, Refresh Token: 7일~30일).
- Refresh Token을 구현하면 Access Token의 만료 시간을 짧게 설정하여 보안을 강화할 수 있습니다.

### OAuth 제공자별 특이사항
- **카카오**: `code` 파라미터만 필요
- **구글**: `code` 파라미터만 필요
- **네이버**: `code`와 `state` 파라미터 모두 필요 (CSRF 방지)

### 코드 재사용 권장사항
- JWT 생성 로직은 공통 유틸리티 클래스로 추출하여 세 개의 컨트롤러에서 공통 사용
- 사용자 조회/저장 로직도 공통 서비스로 추출하여 중복 코드 방지
- 프론트엔드 토큰 저장 로직도 공통 유틸리티 함수로 추출


