# 데이터베이스 마이그레이션 가이드

이 프로젝트는 Alembic을 사용하여 데이터베이스 마이그레이션을 관리합니다.

## 설치

```bash
conda activate torch313
pip install -r requirements.txt
```

## 초기 마이그레이션 생성

처음 설정할 때:

```bash
cd ai
alembic revision --autogenerate -m "Initial migration"
```

## 마이그레이션 실행

```bash
# 최신 마이그레이션 적용
alembic upgrade head

# 특정 리비전으로 업그레이드
alembic upgrade <revision>

# 한 단계 롤백
alembic downgrade -1

# 특정 리비전으로 다운그레이드
alembic downgrade <revision>
```

## 마이그레이션 상태 확인

```bash
# 현재 마이그레이션 상태 확인
alembic current

# 마이그레이션 히스토리 확인
alembic history
```

## 새 마이그레이션 생성

모델을 변경한 후:

```bash
# 자동으로 변경사항 감지하여 마이그레이션 생성
alembic revision --autogenerate -m "설명"

# 수동으로 마이그레이션 생성
alembic revision -m "설명"
```

## 주의사항

1. **프로덕션 환경에서는 반드시 Alembic을 사용하세요**
   - `scripts/init_db.py`는 개발 환경에서만 사용

2. **마이그레이션 파일은 버전 관리에 포함되어야 합니다**
   - `alembic/versions/` 디렉토리의 파일들을 Git에 커밋

3. **환경 변수 설정**
   - `.env` 파일에 `NEON_DATABASE_URL`이 설정되어 있어야 합니다

## 문제 해결

### 마이그레이션 실행 시 에러 발생

1. 데이터베이스 연결 확인:
   ```bash
   # .env 파일 확인
   cat .env | grep NEON_DATABASE_URL
   ```

2. 마이그레이션 히스토리 확인:
   ```bash
   alembic history
   alembic current
   ```

3. 강제로 특정 리비전으로 설정 (주의: 데이터 손실 가능):
   ```bash
   alembic stamp <revision>
   ```

