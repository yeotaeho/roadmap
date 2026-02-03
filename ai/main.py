from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import logging
import sys
import os
from pathlib import Path

# Configure logging first
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

# Import routers
# News router는 OAuth에 의존하지 않으므로 먼저 import
news_router = None
try:
    from api.v1.news.news_routor import router as news_router
    logger.info("News router imported successfully")
except Exception as e:
    logger.warning(f"News router import failed: {e}")
    news_router = None

# OAuth router는 settings에 의존하므로 환경 변수가 필요
oauth_router = None
try:
    from api.v1.oauth.oauth_routor import router as oauth_router
    logger.info("OAuth router imported successfully")
except Exception as e:
    logger.warning(f"OAuth router import failed: {e}")
    logger.warning("OAuth router requires environment variables. Continuing without OAuth support.")
    oauth_router = None

# User router
user_router = None
try:
    from api.v1.user.user_routor import router as user_router
    logger.info("User router imported successfully")
except Exception as e:
    logger.warning(f"User router import failed: {e}")
    user_router = None

# Create FastAPI app
app = FastAPI(
    title="ESG API Gateway",
    description="Python FastAPI Gateway for Spring Boot Services and OAuth",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
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

# Register routers
if oauth_router:
    app.include_router(oauth_router, prefix="/api")
    logger.info("OAuth router registered")

if news_router:
    app.include_router(news_router, prefix="/api")
    logger.info("News router registered")

if user_router:
    app.include_router(user_router, prefix="/api")
    logger.info("User router registered")


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
            "user": "/api/user"
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

