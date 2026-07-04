# 백엔드 모듈러 모놀리스(FastAPI + APScheduler)를 단일 이미지로 빌드한다.
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# 시스템 의존성 — psycopg/asyncpg 빌드·libpq 런타임, 헬스체크용 curl.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 의존성 먼저 설치 — 코드만 바뀌면 이 레이어를 재사용한다(빌드 캐싱).
# torch 는 CPU 전용 휠로 먼저 설치해 CUDA 의존성(수 GB) 유입을 막는다. 서버는 CPU 추론(TimesFM).
# 이후 requirements 의 torch 요구는 이미 충족돼 재설치되지 않는다. GPU 호스트면 이 줄을 제거한다.
# BuildKit 캐시 마운트 — 받은 휠을 빌드 간 보존해 재빌드·중단 후 재개를 빠르게.
COPY requirements.txt ./
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip \
    && pip install "torch>=2.0.0" --index-url https://download.pytorch.org/whl/cpu \
    && pip install -r requirements.txt

# 애플리케이션 코드 복사(.dockerignore 로 캐시·비밀 제외).
COPY . .

# 엔트리포인트 — Windows 작성 대비 CRLF 제거·실행권한 부여(root 단계에서).
RUN sed -i 's/\r$//' docker-entrypoint.sh && chmod +x docker-entrypoint.sh

# 비root 실행(보안).
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# 부팅 시 alembic upgrade(RUN_MIGRATIONS 게이팅) 후 CMD 실행.
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
