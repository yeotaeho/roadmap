"""
OAuth 서비스 독립 실행 스크립트

이 파일은 OAuth 도메인 서비스를 독립적으로 실행할 수 있도록 합니다.
FastAPI 앱을 생성하고 OAuth 라우터를 등록한 후 uvicorn으로 서버를 시작합니다.

사용법:
    python main.py
    또는
    python -m domain.oauth.main
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
import sys
from pathlib import Path

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# 프로젝트 루트를 Python 경로에 추가
# ai/domain/oauth/main.py -> ai/
PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# OAuth 라우터 import
try:
    # sys.path에 프로젝트 루트가 추가된 상태에서 일반 import 사용
    # oauth_routor.py 내부의 sys.path 조작과 충돌하지 않도록 주의
    import api.v1.oauth.oauth_routor
    oauth_router = api.v1.oauth.oauth_routor.router
    logger.info("OAuth router imported successfully")
except ImportError as e:
    logger.error(f"OAuth router import failed: {e}")
    logger.error(f"PROJECT_ROOT: {PROJECT_ROOT}")
    logger.error(f"Trying alternative import method...")
    try:
        # 대안: 직접 파일 경로로 import
        import importlib.util
        oauth_routor_path = PROJECT_ROOT / "api" / "v1" / "oauth" / "oauth_routor.py"
        spec = importlib.util.spec_from_file_location("api.v1.oauth.oauth_routor", oauth_routor_path)
        if spec and spec.loader:
            oauth_routor_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(oauth_routor_module)
            oauth_router = oauth_routor_module.router
            logger.info("OAuth router imported successfully (alternative method)")
        else:
            raise ImportError("Could not create module spec")
    except Exception as e2:
        logger.error(f"Alternative import also failed: {e2}", exc_info=True)
        oauth_router = None
except Exception as e:
    logger.error(f"OAuth router import failed: {e}", exc_info=True)
    oauth_router = None

# FastAPI 앱 생성
app = FastAPI(
    title="OAuth Service",
    description="Python FastAPI OAuth Service (Google, Kakao, Naver)",
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

# OAuth 라우터 등록
if oauth_router:
    app.include_router(oauth_router, prefix="/api")
    logger.info("OAuth router registered at /api/oauth")
else:
    logger.warning("OAuth router not registered - service may not function correctly")


@app.get("/")
async def root():
    """루트 엔드포인트"""
    return {
        "message": "OAuth Service",
        "version": "1.0.0",
        "service": "oauth",
        "docs": "/docs",
        "endpoints": {
            "oauth": "/api/oauth",
            "google_login": "/api/oauth/google/login",
            "kakao_login": "/api/oauth/kakao/login",
            "naver_login": "/api/oauth/naver/login",
            "signup": "/api/oauth/signup",
            "refresh": "/api/oauth/refresh",
            "logout": "/api/oauth/logout"
        }
    }


@app.get("/health")
async def health_check():
    """헬스 체크 엔드포인트"""
    return {
        "status": "healthy",
        "service": "OAuth Service",
        "version": "1.0.0"
    }


if __name__ == "__main__":
    import uvicorn
    
    # 설정에서 포트를 가져오거나 기본값 사용
    # 기본 포트 8001 (메인 게이트웨이 8000과 구분)
    port = 8001
    
    logger.info(f"Starting OAuth Service on port {port}")
    logger.info(f"API Documentation: http://localhost:{port}/docs")
    logger.info(f"Health Check: http://localhost:{port}/health")
    
    # import string 방식으로 실행 (reload 지원)
    # 현재 파일이 domain/oauth/main.py이므로 모듈 경로는 domain.oauth.main
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info"
    )
