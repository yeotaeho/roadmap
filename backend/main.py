from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import logging
import sys
import os
from pathlib import Path

from core.logging_config import setup_logging

setup_logging(level=logging.INFO)

logger = logging.getLogger(__name__)

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

# ---------------------------------------------------------------------------
# API v1 라우터 (단일 진입점에서 명시 등록)
# 각 APIRouter 에 이미 prefix=/oauth | /news | /user 가 있으므로
# include_router(..., prefix="/api") 와 결합 시 최종 경로는 /api/oauth, ...
# ---------------------------------------------------------------------------
from api.v1.master.master_routor import router as master_v1_router
from api.v1.news.news_routor import router as news_v1_router
from api.v1.oauth.oauth_routor import router as oauth_v1_router
from api.v1.user.user_routor import router as user_v1_router
from core.scheduler import start_scheduler, stop_scheduler

API_V1_PREFIX = "/api"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI 라이프사이클 — APScheduler 자동 수집 스케줄러 시작/종료."""
    start_scheduler()
    try:
        yield
    finally:
        stop_scheduler()


# Create FastAPI app
app = FastAPI(
    title="ESG API Gateway",
    description="Python FastAPI Gateway for Spring Boot Services and OAuth",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS 설정
# allow_credentials=True일 때는 와일드카드(*)를 사용할 수 없으므로 명시적으로 origin 지정
cors_origins = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:3000,http://localhost:3001"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in cors_origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 전역 예외 핸들러
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """전역 예외 핸들러"""
    logger.error(f"Unhandled exception: {type(exc).__name__} - {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )

# Pydantic Validation 에러 핸들러
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Pydantic validation 에러 핸들러"""
    logger.warning(f"Validation error: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()}
    )

# Register routers (전 서비스 라우터 고정 연결)
app.include_router(oauth_v1_router, prefix=API_V1_PREFIX)
app.include_router(news_v1_router, prefix=API_V1_PREFIX)
app.include_router(user_v1_router, prefix=API_V1_PREFIX)
app.include_router(master_v1_router, prefix=API_V1_PREFIX)
logger.info(
    "Routers registered: %s/oauth, %s/news, %s/user, %s/master",
    API_V1_PREFIX,
    API_V1_PREFIX,
    API_V1_PREFIX,
    API_V1_PREFIX,
)


@app.get("/")
async def root():
    """루트 엔드포인트"""
    return {
        "message": "ESG API Gateway",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "oauth": "/api/oauth",
            "news": "/api/news",
            "user": "/api/user",
            "master": "/api/master",
        }
    }


@app.get("/health")
async def health_check():
    """헬스 체크 엔드포인트"""
    return {
        "status": "healthy",
        "service": "ESG API Gateway"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )

