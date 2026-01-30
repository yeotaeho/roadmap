import asyncio
import httpx
from typing import List, Optional
import logging
from bs4 import BeautifulSoup
from datetime import datetime
from ..model.news_article import NewsArticle
from ..config.rss_url_mapper import RssUrlMapper
from .rss_service import RssService

logger = logging.getLogger(__name__)


class NewsService:
    """뉴스 서비스 (RSS 및 네이버 API 통합)"""
    
    def __init__(self, naver_client_id: str, naver_client_secret: str):
        """
        NewsService 초기화
        
        Args:
            naver_client_id: 네이버 API 클라이언트 ID
            naver_client_secret: 네이버 API 클라이언트 시크릿
        """
        self.naver_client_id = naver_client_id
        self.naver_client_secret = naver_client_secret
        self.rss_service = RssService()
        self.rss_url_mapper = RssUrlMapper()
        self.naver_api_url = "https://openapi.naver.com/v1/search/news.json"
    
    async def search_news(
        self, 
        query: str, 
        display: Optional[int] = None, 
        start: Optional[int] = None
    ) -> List[NewsArticle]:
        """
        뉴스 검색 (RSS 우선, 필요시 네이버 API)
        
        Args:
            query: 검색어 또는 카테고리명
            display: 표시할 결과 수
            start: 시작 위치
            
        Returns:
            뉴스 기사 목록
        """
        if self.rss_url_mapper.is_category(query):
            logger.info(f"카테고리로 인식: query={query}, RSS 피드 사용")
            return await self._search_news_from_rss(query, display, start)
        else:
            logger.info(f"검색어로 인식: query={query}, 네이버 API 사용")
            return await self._search_news_from_naver_api(query, display, start)
    
    async def _search_news_from_rss(
        self, 
        category: str, 
        display: Optional[int], 
        start: Optional[int]
    ) -> List[NewsArticle]:
        """RSS 피드를 통한 뉴스 검색 (비동기 병렬 처리)"""
        try:
            rss_urls = self.rss_url_mapper.get_rss_urls_by_category(category)
            
            if not rss_urls:
                logger.warning(f"카테고리에 해당하는 RSS URL이 없습니다: category={category}")
                return []
            
            logger.info(f"RSS 피드 수집 시작: category={category}, RSS URL 개수={len(rss_urls)}")
            
            # 비동기 병렬 처리로 여러 RSS 피드 수집
            all_articles = await self._fetch_multiple_rss_feeds(rss_urls)
            
            logger.info(f"RSS 피드 수집 완료: category={category}, 총 기사 수={len(all_articles)}")
            
            # 중복 제거 (제목 기준)
            unique_articles = self._remove_duplicates(all_articles)
            
            logger.info(f"중복 제거 후 기사 수: category={category}, 기사 수={len(unique_articles)}")
            
            # 페이징 처리
            return self._apply_paging(unique_articles, display, start)
            
        except Exception as e:
            logger.error(f"RSS 뉴스 검색 실패: category={category}, error={e}", exc_info=True)
            return []
    
    async def _fetch_multiple_rss_feeds(self, rss_urls: List[str]) -> List[NewsArticle]:
        """여러 RSS 피드를 비동기 병렬로 수집"""
        # 동기 함수를 비동기로 실행
        loop = asyncio.get_event_loop()
        tasks = [
            loop.run_in_executor(None, self.rss_service.fetch_news_from_rss, url)
            for url in rss_urls
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        all_articles = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"RSS 피드 수집 실패: URL={rss_urls[i]}, error={result}")
                continue
            all_articles.extend(result)
        
        return all_articles
    
    def _remove_duplicates(self, articles: List[NewsArticle]) -> List[NewsArticle]:
        """중복 제거 (제목 기준)"""
        seen = set()
        unique = []
        for article in articles:
            if article.title not in seen:
                seen.add(article.title)
                unique.append(article)
        return unique
    
    def _apply_paging(
        self, 
        articles: List[NewsArticle], 
        display: Optional[int], 
        start: Optional[int]
    ) -> List[NewsArticle]:
        """페이징 처리"""
        display = display or 20
        start = start or 1
        
        offset = start - 1
        from_index = min(offset, len(articles))
        to_index = min(from_index + display, len(articles))
        
        if from_index >= to_index:
            return []
        
        return articles[from_index:to_index]
    
    async def _search_news_from_naver_api(
        self, 
        query: str, 
        display: Optional[int], 
        start: Optional[int]
    ) -> List[NewsArticle]:
        """네이버 API를 통한 뉴스 검색"""
        try:
            display = display or 20
            start = start or 1
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    self.naver_api_url,
                    params={
                        "query": query,
                        "display": display,
                        "start": start,
                        "sort": "date"
                    },
                    headers={
                        "X-Naver-Client-Id": self.naver_client_id,
                        "X-Naver-Client-Secret": self.naver_client_secret
                    }
                )
                response.raise_for_status()
                data = response.json()
                
                articles = []
                items = data.get("items", [])
                
                # 날짜순 정렬 (최신이 먼저)
                items.sort(key=lambda x: self._parse_naver_date(x.get("pubDate", "")), reverse=True)
                
                for item in items:
                    try:
                        article = self._convert_naver_item_to_article(item, query)
                        articles.append(article)
                    except Exception as e:
                        logger.warning(f"네이버 기사 변환 실패: {e}")
                        continue
                
                logger.info(f"네이버 뉴스 API 응답: 총 {len(articles)}개 기사")
                return articles
                
        except Exception as e:
            logger.error(f"네이버 뉴스 API 호출 실패: {e}", exc_info=True)
            return []
    
    def _convert_naver_item_to_article(self, item: dict, query: str) -> NewsArticle:
        """네이버 뉴스 아이템을 NewsArticle로 변환"""
        # HTML 태그 제거
        title = self._clean_html(item.get("title", ""))
        description = self._clean_html(item.get("description", ""))
        
        # 날짜 포맷팅 (RFC 822 -> yyyy.MM.dd)
        date = self._format_naver_date(item.get("pubDate", ""))
        
        # 이미지 추출
        image_url = self._extract_image_from_description(item.get("description", ""))
        
        return NewsArticle(
            type=query or "뉴스",
            title=title,
            date=date,
            image=image_url,
            link=item.get("link", ""),
            description=description
        )
    
    def _clean_html(self, html: str) -> str:
        """HTML 태그 제거"""
        if not html:
            return ""
        
        try:
            soup = BeautifulSoup(html, "html.parser")
            text = soup.get_text()
            # HTML 엔티티 디코딩
            text = text.replace("&quot;", "\"").replace("&amp;", "&")
            text = text.replace("&lt;", "<").replace("&gt;", ">")
            return text.strip()
        except Exception as e:
            logger.warning(f"HTML 정리 실패: {e}")
            return html
    
    def _format_naver_date(self, pub_date: str) -> str:
        """네이버 API 날짜 포맷팅 (RFC 822 -> yyyy.MM.dd)"""
        if not pub_date:
            return datetime.now().strftime("%Y.%m.%d")
        
        try:
            # RFC 822 형식 파싱 (예: "Wed, 13 Dec 2025 10:30:00 +0900")
            # Python의 email.utils.parsedate_to_datetime 사용
            from email.utils import parsedate_to_datetime
            dt = parsedate_to_datetime(pub_date)
            return dt.strftime("%Y.%m.%d")
        except Exception as e:
            logger.warning(f"날짜 포맷팅 실패: pubDate={pub_date}, {e}")
            return datetime.now().strftime("%Y.%m.%d")
    
    def _parse_naver_date(self, pub_date: str) -> datetime:
        """네이버 API 날짜를 datetime으로 파싱 (정렬용)"""
        try:
            from email.utils import parsedate_to_datetime
            return parsedate_to_datetime(pub_date)
        except:
            return datetime.min
    
    def _extract_image_from_description(self, description: str) -> str:
        """설명에서 이미지 URL 추출"""
        if not description:
            return "https://placehold.co/400x250/000000/FFFFFF?text=NEWS"
        
        try:
            soup = BeautifulSoup(description, "html.parser")
            img = soup.find("img")
            
            if img:
                # src, data-src 순서로 확인
                for attr in ["src", "data-src", "data-lazy-src"]:
                    url = img.get(attr, "")
                    if url:
                        if url.startswith("//"):
                            return "https:" + url
                        elif url.startswith("http://") or url.startswith("https://"):
                            return url
        except Exception as e:
            logger.debug(f"이미지 추출 실패: {e}")
        
        return "https://placehold.co/400x250/000000/FFFFFF?text=NEWS"

