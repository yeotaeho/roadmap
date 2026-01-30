# OAuth Domain 아키텍처 문서

## 개요

이 문서는 OAuth Domain 모듈의 아키텍처와 설계 원칙을 설명합니다.

## 아키텍처 패턴

### 계층형 아키텍처 (Layered Architecture)

```
┌─────────────────────────────────────┐
│         API Layer (FastAPI)         │
│      (api/v1/oauth/oauth_routor)    │
└─────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────┐
│      Service Layer (Business)       │
│  (google_oauth_service, user_service)│
└─────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────┐
│    Repository Layer (Data Access)   │
│        (user_repository)            │
└─────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────┐
│      Model Layer (Domain)           │
│            (user.py)                │
└─────────────────────────────────────┘
```

## 컴포넌트 상세

### 1. API Layer

**책임:**
- HTTP 요청/응답 처리
- 요청 검증 (Pydantic)
- 의존성 주입 (FastAPI Depends)
- 에러 처리

**구현:**
- `api/v1/oauth/oauth_routor.py`

### 2. Service Layer

**책임:**
- 비즈니스 로직 구현
- OAuth 플로우 처리
- 사용자 관리 로직
- 토큰 관리 로직

**주요 서비스:**

#### OAuth Services
- `GoogleOAuthService`: Google OAuth 플로우
- `KakaoOAuthService`: Kakao OAuth 플로우
- `NaverOAuthService`: Naver OAuth 플로우

#### Business Services
- `UserService`: 사용자 CRUD 및 비즈니스 로직
- `RefreshTokenService`: 리프레시 토큰 관리

### 3. Repository Layer

**책임:**
- 데이터 접근 추상화
- SQL 쿼리 실행
- 트랜잭션 관리

**구현:**
- `repository/user_repository.py`

### 4. Model Layer

**책임:**
- 도메인 모델 정의
- 데이터베이스 스키마 매핑

**구현:**
- `model/user.py`

## 의존성 흐름

```
API Router
    ↓
Services (OAuth, User, RefreshToken)
    ↓
Repositories (UserRepository)
    ↓
Models (User)
    ↓
Database (PostgreSQL)
```

## 보안 아키텍처

### 1. 인증 플로우

```
Client → API Router → OAuth Service → OAuth Provider
                ↓
         State + PKCE 생성
                ↓
         Redis 저장
                ↓
         인증 URL 반환
```

### 2. 콜백 플로우

```
OAuth Provider → Client → API Router
                              ↓
                    State 검증 (Redis)
                              ↓
                    PKCE 검증 (Redis)
                              ↓
                    토큰 교환
                              ↓
                    사용자 정보 조회
                              ↓
                    사용자 조회/생성
                              ↓
                    JWT 토큰 생성
                              ↓
                    리프레시 토큰 저장 (Redis)
                              ↓
                    응답 반환
```

### 3. 토큰 갱신 플로우

```
Client → API Router → RefreshTokenService
                ↓
         리프레시 토큰 검증 (Redis)
                ↓
         JWT 검증
                ↓
         새 토큰 생성
                ↓
         토큰 로테이션 (Redis)
                ↓
         응답 반환
```

## 데이터 흐름

### 1. 사용자 생성 플로우

```
OAuth 콜백
    ↓
사용자 정보 추출
    ↓
기존 사용자 조회 (Repository)
    ↓
없으면 → 신규 사용자 생성 (Repository)
있으면 → 사용자 정보 업데이트 (Repository)
    ↓
JWT 토큰 생성 (JWTService)
    ↓
리프레시 토큰 저장 (RefreshTokenService → Redis)
    ↓
응답 반환
```

### 2. 회원가입 플로우

```
회원가입 토큰 검증 (SignupTokenService)
    ↓
OAuth 정보 추출
    ↓
사용자 생성 (UserService → Repository)
    ↓
JWT 토큰 생성
    ↓
리프레시 토큰 저장
    ↓
응답 반환
```

## 외부 의존성

### 1. PostgreSQL
- **용도**: 사용자 정보 저장
- **연결**: SQLAlchemy (비동기)
- **드라이버**: asyncpg

### 2. Redis
- **용도**: 
  - State 저장 (CSRF 방지)
  - PKCE Code Verifier 저장
  - 리프레시 토큰 저장
- **연결**: redis.asyncio

### 3. OAuth Providers
- **Google**: OAuth 2.0
- **Kakao**: OAuth 2.0
- **Naver**: OAuth 2.0

## 설계 원칙

### 1. 단일 책임 원칙 (SRP)
- 각 서비스는 하나의 책임만 가짐
- 예: `GoogleOAuthService`는 Google OAuth만 처리

### 2. 의존성 역전 원칙 (DIP)
- 고수준 모듈이 저수준 모듈에 의존하지 않음
- 인터페이스를 통한 의존성 주입

### 3. 관심사의 분리 (SoC)
- API, 비즈니스 로직, 데이터 접근 분리
- 각 계층의 책임 명확화

### 4. DRY (Don't Repeat Yourself)
- 공통 로직은 유틸리티로 분리
- 예: JWT, PKCE, State 관리

## 확장성 고려사항

### 1. 새로운 OAuth 제공자 추가

1. `service/{provider}_oauth_service.py` 생성
2. `OAuthService` 인터페이스 구현
3. 라우터에 엔드포인트 추가

### 2. 데이터베이스 변경

- Repository 패턴으로 데이터 접근 추상화
- 다른 데이터베이스로 변경 시 Repository만 수정

### 3. 캐싱 전략

- Redis를 활용한 캐싱 가능
- 사용자 정보 캐싱 등 확장 가능

## 성능 최적화

### 1. 비동기 처리
- 모든 I/O 작업은 비동기로 처리
- FastAPI + async/await 활용

### 2. 연결 풀링
- 데이터베이스 연결 풀 사용
- Redis 연결 재사용

### 3. 캐싱
- State, PKCE는 Redis에 저장 (빠른 조회)
- 리프레시 토큰도 Redis에 저장

## 모니터링 및 로깅

### 로깅 레벨
- INFO: 일반적인 작업 로그
- WARN: 경고 상황
- ERROR: 에러 상황

### 주요 로그 포인트
- OAuth 플로우 시작/완료
- 토큰 생성/검증
- 사용자 생성/업데이트
- 에러 발생 시점

## 테스트 전략

### 단위 테스트
- 각 서비스의 메서드별 테스트
- Mock을 사용한 외부 의존성 격리

### 통합 테스트
- API 엔드포인트 테스트
- 실제 데이터베이스/Redis 사용

### E2E 테스트
- 전체 OAuth 플로우 테스트
- 실제 OAuth 제공자와 통신

