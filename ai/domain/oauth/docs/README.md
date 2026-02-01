# OAuth Domain 모듈 문서

## 개요

이 모듈은 Google, Kakao, Naver OAuth 인증을 지원하는 Python 기반 OAuth 서비스입니다. Spring Boot로 구현된 OAuth 서비스를 Python으로 포팅한 것으로, 동일한 기능과 보안 수준을 제공합니다.

## 주요 기능

- ✅ **다중 OAuth 제공자 지원**: Google, Kakao, Naver
- ✅ **보안 기능**: State 검증, PKCE 지원
- ✅ **JWT 토큰 관리**: 액세스 토큰 및 리프레시 토큰
- ✅ **사용자 관리**: PostgreSQL 기반 사용자 정보 저장
- ✅ **토큰 관리**: Redis 기반 리프레시 토큰 관리
- ✅ **회원가입 플로우**: 토큰 기반 회원가입 처리

## 아키텍처

```
domain/oauth/
├── config/          # 설정 관리
│   ├── settings.py  # 환경변수 설정 (Pydantic)
│   └── database.py  # 데이터베이스 연결 설정
├── model/           # 데이터 모델
│   └── user.py      # User 엔티티 (SQLAlchemy)
├── repository/      # 데이터 접근 계층
│   └── user_repository.py
├── service/         # 비즈니스 로직
│   ├── google_oauth_service.py
│   ├── kakao_oauth_service.py
│   ├── naver_oauth_service.py
│   ├── user_service.py
│   └── refresh_token_service.py
├── util/            # 유틸리티
│   ├── jwt.py       # JWT 토큰 생성/검증
│   ├── pkce.py      # PKCE 생성
│   ├── state.py     # OAuth State 관리
│   └── signup_token.py  # 회원가입 토큰
└── base/            # 기본 클래스
```

## 주요 컴포넌트

### 1. Config (설정)

#### `config/settings.py`
- Pydantic Settings를 사용한 환경변수 관리
- 데이터베이스, Redis, JWT, OAuth 제공자 설정

#### `config/database.py`
- SQLAlchemy 비동기 엔진 설정
- 데이터베이스 세션 관리

### 2. Model (데이터 모델)

#### `model/user.py`
- User 엔티티 정의
- OAuth 제공자별 사용자 정보 저장
- 필드:
  - `id`: 사용자 ID (Primary Key)
  - `provider`: OAuth 제공자 (kakao, google, naver)
  - `provider_id`: 제공자별 고유 ID
  - `email`: 이메일
  - `name`: 이름
  - `nickname`: 닉네임
  - `profile_image`: 프로필 이미지 URL
  - `role`: 사용자 권한 (기본값: USER)
  - `created_at`, `updated_at`: 타임스탬프

### 3. Repository (데이터 접근)

#### `repository/user_repository.py`
- 사용자 CRUD 작업
- 주요 메서드:
  - `find_by_provider_and_provider_id()`: 제공자별 사용자 조회
  - `find_by_id()`: ID로 사용자 조회
  - `save()`: 사용자 저장/업데이트
  - `delete()`: 사용자 삭제
  - `delete_duplicates()`: 중복 레코드 삭제

### 4. Service (비즈니스 로직)

#### `service/google_oauth_service.py`
- Google OAuth 플로우 처리
- 주요 메서드:
  - `get_authorization_url()`: 인증 URL 생성 (State + PKCE)
  - `get_access_token()`: 액세스 토큰 발급
  - `get_user_info()`: 사용자 정보 조회
  - `process_oauth()`: 전체 OAuth 플로우 실행

#### `service/kakao_oauth_service.py`
- Kakao OAuth 플로우 처리
- Google과 동일한 인터페이스

#### `service/naver_oauth_service.py`
- Naver OAuth 플로우 처리
- State 검증 지원 (PKCE 미지원)

#### `service/user_service.py`
- 사용자 관리 로직
- 주요 메서드:
  - `find_or_create_user()`: 사용자 찾기 또는 생성
  - `find_user()`: 사용자 찾기 (생성하지 않음)
  - `find_by_id()`: ID로 사용자 찾기
  - `save()`: 사용자 저장

#### `service/refresh_token_service.py`
- 리프레시 토큰 관리 (Redis)
- 주요 메서드:
  - `save_refresh_token()`: 토큰 저장
  - `validate_refresh_token()`: 토큰 검증
  - `delete_refresh_token()`: 토큰 삭제
  - `invalidate_all_user_tokens()`: 사용자 모든 토큰 무효화
  - `rotate_refresh_token()`: 토큰 로테이션

### 5. Util (유틸리티)

#### `util/jwt.py`
- JWT 토큰 생성 및 검증
- HS512 알고리즘 사용
- 주요 메서드:
  - `generate_token()`: 액세스 토큰 생성 (30분)
  - `generate_refresh_token()`: 리프레시 토큰 생성 (21일)
  - `decode_token()`: 토큰 디코딩 및 검증
  - `extract_user_id()`: 사용자 ID 추출
  - `extract_provider()`: 제공자 추출
  - `validate_token()`: 토큰 유효성 검증

#### `util/pkce.py`
- PKCE (Proof Key for Code Exchange) 생성
- 주요 메서드:
  - `generate_code_verifier()`: Code Verifier 생성
  - `generate_code_challenge()`: Code Challenge 생성 (SHA-256)
  - `store_code_verifier()`: Redis에 저장
  - `get_and_remove_code_verifier()`: 조회 및 삭제

#### `util/state.py`
- OAuth State 파라미터 관리 (CSRF 방지)
- 주요 메서드:
  - `generate_and_store_state()`: State 생성 및 Redis 저장 (10분 TTL)
  - `validate_and_remove_state()`: State 검증 및 삭제 (1회용)

#### `util/signup_token.py`
- 회원가입 임시 토큰 관리
- 주요 메서드:
  - `generate_signup_token()`: 회원가입 토큰 생성 (10분 TTL)
  - `validate_signup_token()`: 토큰 검증
  - `extract_oauth_info()`: OAuth 정보 추출

## 설정 방법

### 1. 환경변수 설정

`.env` 파일 생성:

```env
# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/dbname
DATABASE_USER=user
DATABASE_PASSWORD=password

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_SSL_ENABLED=true

# JWT
JWT_SECRET=your-secret-key-minimum-64-bytes-for-hs512
JWT_EXPIRATION=1800000
JWT_REFRESH_EXPIRATION=1814400000

# Google OAuth
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
GOOGLE_REDIRECT_URI=http://localhost:3000/auth/google/callback

# Kakao OAuth
KAKAO_CLIENT_ID=your-kakao-client-id
KAKAO_CLIENT_SECRET=your-kakao-client-secret
KAKAO_REDIRECT_URI=http://localhost:3000/auth/kakao/callback
KAKAO_ADMIN_KEY=your-kakao-admin-key

# Naver OAuth
NAVER_CLIENT_ID=your-naver-client-id
NAVER_CLIENT_SECRET=your-naver-client-secret
NAVER_REDIRECT_URI=http://localhost:3000/auth/naver/callback
```

### 2. 데이터베이스 마이그레이션

PostgreSQL 데이터베이스에 `users` 테이블 생성:

```sql
CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    provider VARCHAR(20) NOT NULL,
    provider_id VARCHAR(100) NOT NULL,
    email VARCHAR(100),
    name VARCHAR(100),
    nickname VARCHAR(100),
    profile_image VARCHAR(500),
    role VARCHAR(20) DEFAULT 'USER',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(provider, provider_id)
);

CREATE INDEX idx_users_provider_provider_id ON users(provider, provider_id);
```

### 3. 의존성 설치

```bash
# 메인 requirements.txt 사용 (프로젝트 루트에서)
pip install -r ../../requirements.txt
```

## 사용 방법

### FastAPI 라우터에서 사용

```python
from domain.oauth.service.google_oauth_service import GoogleOAuthService
from domain.oauth.service.user_service import UserService
from domain.oauth.util.jwt import JWTService
from domain.oauth.config.database import get_db

# 의존성 주입
async def get_services(db: AsyncSession = Depends(get_db)):
    state_service = OAuthStateService(redis_client)
    pkce_service = PKCEService(redis_client)
    google_service = GoogleOAuthService(state_service, pkce_service, http_client)
    user_service = UserService(db)
    jwt_service = JWTService()
    return {
        "google_service": google_service,
        "user_service": user_service,
        "jwt_service": jwt_service
    }

# 라우터에서 사용
@router.get("/google/login")
async def get_google_login_url(services: dict = Depends(get_services)):
    google_service = services["google_service"]
    auth_data = await google_service.get_authorization_url()
    return auth_data
```

## OAuth 플로우

### 1. 로그인 URL 요청

```
GET /api/v1/oauth/google/login
→ { "authUrl": "...", "state": "..." }
```

### 2. 사용자 인증 (OAuth 제공자)

사용자가 `authUrl`로 이동하여 인증

### 3. 콜백 처리

```
POST /api/v1/oauth/google/callback
Body: { "code": "...", "state": "..." }
```

**신규 사용자인 경우:**
```json
{
  "success": false,
  "isNewUser": true,
  "message": "회원가입이 필요합니다.",
  "signupToken": "..."
}
```

**기존 사용자인 경우:**
```json
{
  "success": true,
  "isNewUser": false,
  "message": "구글 로그인 성공",
  "userId": 1,
  "email": "user@example.com",
  "accessToken": "...",
  "tokenType": "Bearer"
}
```

### 4. 회원가입 (신규 사용자)

```
POST /api/v1/oauth/signup
Body: { "signupToken": "..." }
```

### 5. 토큰 갱신

```
POST /api/v1/oauth/refresh
Cookie: refreshToken=...
```

## 보안 기능

### 1. State 검증 (CSRF 방지)
- OAuth 요청 시 랜덤 State 생성
- Redis에 저장 (10분 TTL)
- 콜백 시 검증 후 삭제 (1회용)

### 2. PKCE (Proof Key for Code Exchange)
- Google, Kakao 지원
- Code Verifier 생성 및 SHA-256 해시
- Redis에 저장 (10분 TTL)
- 토큰 교환 시 검증

### 3. JWT 토큰
- HS512 알고리즘 사용
- 액세스 토큰: 30분 만료
- 리프레시 토큰: 21일 만료
- 토큰 로테이션 지원

### 4. 리프레시 토큰 관리
- Redis에 저장
- 사용자별 토큰 목록 관리
- 강제 로그아웃 시 모든 토큰 무효화

## API 엔드포인트

### Google OAuth
- `GET /api/v1/oauth/google/login` - 로그인 URL 요청
- `POST /api/v1/oauth/google/callback` - 콜백 처리

### Kakao OAuth
- `GET /api/v1/oauth/kakao/login` - 로그인 URL 요청
- `POST /api/v1/oauth/kakao/callback` - 콜백 처리

### Naver OAuth
- `GET /api/v1/oauth/naver/login` - 로그인 URL 요청
- `POST /api/v1/oauth/naver/callback` - 콜백 처리

### 회원가입
- `POST /api/v1/oauth/signup` - OAuth 회원가입

### 토큰 관리
- `POST /api/v1/oauth/refresh` - 토큰 갱신
- `POST /api/v1/oauth/logout` - 로그아웃
- `POST /api/v1/oauth/force-logout/{user_id}` - 강제 로그아웃

## 데이터베이스 스키마

### users 테이블

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | BIGSERIAL | Primary Key |
| provider | VARCHAR(20) | OAuth 제공자 |
| provider_id | VARCHAR(100) | 제공자별 고유 ID |
| email | VARCHAR(100) | 이메일 |
| name | VARCHAR(100) | 이름 |
| nickname | VARCHAR(100) | 닉네임 |
| profile_image | VARCHAR(500) | 프로필 이미지 URL |
| role | VARCHAR(20) | 사용자 권한 (기본: USER) |
| created_at | TIMESTAMP | 생성 시간 |
| updated_at | TIMESTAMP | 수정 시간 |

**인덱스:**
- `UNIQUE(provider, provider_id)`: 제공자별 고유 제약

## Redis 키 구조

### State 관리
- 키: `oauth:state:{state}`
- 값: `"valid"`
- TTL: 10분

### PKCE Code Verifier
- 키: `oauth:pkce:{state}`
- 값: `code_verifier`
- TTL: 10분

### 리프레시 토큰
- 키: `refreshToken:{refresh_token}`
- 값: `user_id`
- TTL: 21일

### 사용자별 토큰 목록
- 키: `user:tokens:{user_id}`
- 값: Set of refresh tokens
- TTL: 21일

## 에러 처리

### 일반적인 에러 응답 형식

```json
{
  "success": false,
  "message": "에러 메시지",
  "error": "ErrorType"
}
```

### 주요 에러 코드

- `400`: 잘못된 요청 (State 누락 등)
- `401`: 인증 실패 (토큰 만료, 무효화 등)
- `500`: 서버 오류

## 테스트

### 로컬 테스트

```bash
# 환경변수 설정
export DATABASE_URL="postgresql+asyncpg://user:pass@localhost/db"
export REDIS_HOST="localhost"
export JWT_SECRET="your-secret-key"

# 서버 실행
python main.py
```

### API 테스트

```bash
# 로그인 URL 요청
curl http://localhost:8000/api/v1/oauth/google/login

# 콜백 처리
curl -X POST http://localhost:8000/api/v1/oauth/google/callback \
  -H "Content-Type: application/json" \
  -d '{"code": "...", "state": "..."}'
```

## 주의사항

1. **JWT Secret**: 최소 64바이트 (HS512 알고리즘)
2. **Redis 연결**: SSL 설정 확인 (Upstash 사용 시)
3. **데이터베이스**: 비동기 드라이버 사용 (asyncpg)
4. **토큰 보안**: 리프레시 토큰은 HttpOnly 쿠키로 전송 권장
5. **CORS**: 프로덕션에서는 특정 도메인으로 제한

## 참고 자료

- [OAuth 2.0 공식 문서](https://oauth.net/2/)
- [PKCE RFC 7636](https://tools.ietf.org/html/rfc7636)
- [JWT 공식 문서](https://jwt.io/)
- [FastAPI 공식 문서](https://fastapi.tiangolo.com/)

