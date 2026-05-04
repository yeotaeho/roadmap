from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
import os
import logging

# Domain imports
from domain.news.service.news_service import NewsService
from domain.news.model.news_article import NewsArticle

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/news", tags=["news"])

# NewsService 초기화
naver_client_id = os.getenv("NAVER_CLIENT_ID", "")
naver_client_secret = os.getenv("NAVER_CLIENT_SECRET", "")
news_service = NewsService(naver_client_id, naver_client_secret)


@router.get("/search")
async def search_news(
    query: str = Query(default="삼성", description="검색어"),
    display: Optional[int] = Query(default=None, description="표시할 결과 수"),
    start: Optional[int] = Query(default=None, description="시작 위치")
):
    """
    뉴스 검색 (RSS 우선, 필요시 네이버 API)
    - 카테고리명 입력 시: RSS 피드 사용
    - 자유 검색어 입력 시: 네이버 API 사용
    """
    try:
        articles = await news_service.search_news(query, display, start)
        
        return {
            "success": True,
            "articles": [article.dict() for article in articles],
            "count": len(articles)
        }
    except Exception as e:
        logger.error(f"뉴스 검색 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"뉴스 검색 실패: {str(e)}"
        )


@router.get("/latest")
async def get_latest_news(
    display: Optional[int] = Query(default=100, description="표시할 결과 수")
):
    """
    최신 뉴스 조회 (여러 카테고리 통합)
    - 여러 카테고리의 최신 뉴스를 통합하여 반환
    - 중복 제거 및 정렬 처리
    """
    try:
        # Spring Boot와 동일한 카테고리 목록
        categories = ["경제", "개발", "이슈", "정치", "사회", "과학", "기술", "엔터테인먼트", "스포츠", "세계"]
        per_category = 15
        
        all_articles = []
        
        # 각 카테고리별로 뉴스 수집
        for category in categories:
            try:
                articles = await news_service.search_news(category, per_category, 1)
                all_articles.extend(articles)
                logger.info(f"카테고리 '{category}' 뉴스 수집 완료: {len(articles)}개")
            except Exception as e:
                logger.warning(f"카테고리 {category} 뉴스 수집 실패: {e}")
                continue
        
        # 중복 제거 (제목 기준)
        unique_articles = news_service._remove_duplicates(all_articles)
        
        logger.info(f"중복 제거 후 기사 수: {len(unique_articles)}개")
        
        # 요청한 개수만큼만 반환
        final_articles = unique_articles[:display] if display else unique_articles
        
        logger.info(f"최종 반환 기사 수: {len(final_articles)}개")
        
        return {
            "success": True,
            "articles": [article.dict() for article in final_articles],
            "count": len(final_articles)
        }
    except Exception as e:
        logger.error(f"최신 뉴스 조회 실패: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"최신 뉴스 조회 실패: {str(e)}"
        )

