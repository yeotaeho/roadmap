from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
import sys
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
try:
    from api.v1.oauth.oauth_routor import router as oauth_router
except ImportError as e:
    logger.warning(f"OAuth router import failed: {e}")
    oauth_router = None

try:
    from api.v1.news.news_routor import router as news_router
except ImportError as e:
    logger.warning(f"News router import failed: {e}")
    news_router = None

try:
    from api.v1.user.user_routor import router as user_router
except ImportError as e:
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
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 프로덕션에서는 특정 도메인으로 제한
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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

