# OAuth Domain 보안 문서

## 개요

이 문서는 OAuth Domain 모듈의 보안 기능과 구현 방식을 설명합니다.

## 보안 기능

### 1. CSRF 공격 방지 (State 검증)

#### 구현 방식
- OAuth 요청 시 랜덤 UUID State 생성
- Redis에 저장 (10분 TTL)
- 콜백 시 State 검증 후 즉시 삭제 (1회용)

#### 코드 예시
```python
# State 생성
state = await state_service.generate_and_store_state()
# Redis: oauth:state:{state} = "valid" (TTL: 10분)

# State 검증
is_valid = await state_service.validate_and_remove_state(state)
# 검증 후 즉시 삭제하여 재사용 방지
```

#### 보안 효과
- CSRF 공격 방지
- State 재사용 방지 (1회용)
- 만료된 State 자동 삭제

### 2. PKCE (Proof Key for Code Exchange)

#### 구현 방식
- Code Verifier: 128바이트 랜덤 생성 → Base64 URL 인코딩
- Code Challenge: Code Verifier의 SHA-256 해시 → Base64 URL 인코딩
- Redis에 Code Verifier 저장 (10분 TTL)
- 토큰 교환 시 Code Verifier 검증 후 삭제

#### 코드 예시
```python
# Code Verifier 생성
code_verifier = pkce_service.generate_code_verifier()
# 128바이트 랜덤 → Base64 URL 인코딩

# Code Challenge 생성
code_challenge = pkce_service.generate_code_challenge(code_verifier)
# SHA-256 해시 → Base64 URL 인코딩

# Redis 저장
await pkce_service.store_code_verifier(state, code_verifier)
# Redis: oauth:pkce:{state} = code_verifier (TTL: 10분)

# 토큰 교환 시 검증
code_verifier = await pkce_service.get_and_remove_code_verifier(state)
# 검증 후 즉시 삭제
```

#### 보안 효과
- Authorization Code 가로채기 방지
- 모바일 앱 및 SPA에서 안전한 OAuth 구현
- Google, Kakao 지원

### 3. JWT 토큰 보안

#### 알고리즘
- **HS512**: HMAC-SHA512 알고리즘 사용
- **Secret Key**: 최소 64바이트 (512비트)

#### 토큰 구조

**액세스 토큰:**
```json
{
  "userId": 1,
  "provider": "google",
  "email": "user@example.com",
  "name": "User Name",
  "iat": 1234567890,
  "exp": 1234569690,  // 30분 후
  "sub": "1"
}
```

**리프레시 토큰:**
```json
{
  "type": "refresh",
  "userId": 1,
  "provider": "google",
  "email": "user@example.com",
  "name": "User Name",
  "iat": 1234567890,
  "exp": 1234575690,  // 21일 후
  "sub": "1"
}
```

#### 토큰 만료 시간
- **액세스 토큰**: 30분 (1,800,000ms)
- **리프레시 토큰**: 21일 (1,814,400,000ms)

#### 보안 효과
- 짧은 액세스 토큰 만료 시간으로 유출 시 피해 최소화
- 리프레시 토큰은 Redis에서 관리하여 즉시 무효화 가능

### 4. 리프레시 토큰 관리

#### 저장 방식
- Redis에 저장
- 키: `refreshToken:{token}`
- 값: `user_id`
- TTL: 21일

#### 사용자별 토큰 목록
- 키: `user:tokens:{user_id}`
- 값: Set of refresh tokens
- 용도: 강제 로그아웃 시 모든 토큰 무효화

#### 토큰 로테이션
- 리프레시 토큰 갱신 시 이전 토큰 삭제
- 새 토큰 생성 및 저장
- 토큰 재사용 방지

#### 코드 예시
```python
# 토큰 저장
await refresh_token_service.save_refresh_token(user_id, refresh_token)
# Redis: refreshToken:{token} = user_id
# Redis: user:tokens:{user_id} = Set{token}

# 토큰 검증
user_id = await refresh_token_service.validate_refresh_token(token)
# Redis에서 조회하여 유효성 확인

# 토큰 로테이션
await refresh_token_service.rotate_refresh_token(
    user_id, old_token, new_token
)
# 이전 토큰 삭제 → 새 토큰 저장

# 모든 토큰 무효화
await refresh_token_service.invalidate_all_user_tokens(user_id)
# 사용자별 토큰 목록에서 모든 토큰 삭제
```

### 5. 회원가입 토큰

#### 구현 방식
- OAuth 정보를 JWT로 암호화
- 만료 시간: 10분
- 토큰 타입: "signup"

#### 토큰 구조
```json
{
  "provider": "google",
  "providerId": "123456789",
  "email": "user@example.com",
  "name": "User Name",
  "nickname": "nickname",
  "profileImage": "https://...",
  "tokenType": "signup",
  "iat": 1234567890,
  "exp": 1234568490  // 10분 후
}
```

#### 보안 효과
- OAuth 정보를 안전하게 전달
- 짧은 만료 시간으로 재사용 방지
- 토큰 타입 검증으로 오용 방지

## 보안 모범 사례

### 1. 환경변수 관리
- 민감한 정보는 환경변수로 관리
- `.env` 파일은 `.gitignore`에 추가
- 프로덕션에서는 시크릿 관리 시스템 사용

### 2. HTTPS 사용
- 프로덕션에서는 반드시 HTTPS 사용
- 쿠키의 `Secure` 플래그 설정
- `SameSite=None` 설정 (크로스 도메인)

### 3. 쿠키 보안
```python
response.set_cookie(
    key="refreshToken",
    value=refresh_token,
    httponly=True,      # JavaScript 접근 방지
    secure=True,        # HTTPS만 허용
    samesite="none",    # 크로스 도메인 허용
    path="/",
    max_age=1814400    # 21일
)
```

### 4. 입력 검증
- Pydantic을 사용한 요청 검증
- State, Code 파라미터 필수 검증
- SQL Injection 방지 (SQLAlchemy ORM 사용)

### 5. 에러 메시지
- 상세한 에러 정보는 로그에만 기록
- 클라이언트에는 일반적인 메시지만 반환
- 시스템 정보 노출 방지

## 공격 시나리오 및 대응

### 1. CSRF 공격

**공격 시나리오:**
- 공격자가 피해자의 브라우저로 OAuth 요청 전송
- State 없이 요청하면 공격 성공 가능

**대응:**
- State 검증 필수
- State는 1회용 (검증 후 즉시 삭제)
- 만료 시간 10분

### 2. Authorization Code 가로채기

**공격 시나리오:**
- 공격자가 Authorization Code를 가로채서 토큰 교환 시도

**대응:**
- PKCE 사용
- Code Verifier는 서버에만 저장
- Code Challenge만 OAuth 제공자에 전송

### 3. 토큰 탈취

**공격 시나리오:**
- 공격자가 리프레시 토큰을 탈취하여 사용

**대응:**
- 토큰 로테이션 (이전 토큰 즉시 무효화)
- Redis에서 토큰 검증
- 강제 로그아웃 기능 (모든 토큰 무효화)

### 4. 토큰 재사용

**공격 시나리오:**
- 공격자가 만료된 토큰을 재사용 시도

**대응:**
- JWT 만료 시간 검증
- Redis에서 토큰 존재 여부 확인
- State, PKCE는 1회용

## 보안 체크리스트

### 개발 단계
- [ ] 환경변수로 민감 정보 관리
- [ ] State 검증 구현
- [ ] PKCE 구현 (Google, Kakao)
- [ ] JWT Secret 최소 64바이트
- [ ] 토큰 만료 시간 적절히 설정
- [ ] 입력 검증 구현

### 배포 단계
- [ ] HTTPS 사용
- [ ] 쿠키 Secure 플래그 설정
- [ ] CORS 정책 설정
- [ ] 에러 메시지 일반화
- [ ] 로깅 레벨 조정
- [ ] Redis SSL 연결

### 운영 단계
- [ ] 정기적인 토큰 만료 확인
- [ ] 의심스러운 활동 모니터링
- [ ] 보안 업데이트 적용
- [ ] 로그 분석 및 감사

## 참고 자료

- [OAuth 2.0 Security Best Practices](https://datatracker.ietf.org/doc/html/draft-ietf-oauth-security-topics)
- [PKCE RFC 7636](https://tools.ietf.org/html/rfc7636)
- [JWT Best Practices](https://datatracker.ietf.org/doc/html/rfc8725)
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)

