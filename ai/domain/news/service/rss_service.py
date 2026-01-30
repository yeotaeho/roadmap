import feedparser
from bs4 import BeautifulSoup
import re
from typing import List, Optional
from datetime import datetime
import logging
from ..model.news_article import NewsArticle

logger = logging.getLogger(__name__)


class RssService:
    """RSS 피드 파싱 서비스"""
    
    def fetch_news_from_rss(self, rss_url: str) -> List[NewsArticle]:
        """
        RSS 피드에서 뉴스 기사 목록 반환
        
        Args:
            rss_url: RSS 피드 URL
            
        Returns:
            뉴스 기사 목록
        """
        try:
            feed = feedparser.parse(rss_url)
            
            if feed.bozo:
                logger.warning(f"RSS 피드 파싱 오류: {rss_url}, {feed.bozo_exception}")
            
            articles = []
            for entry in feed.entries:
                try:
                    article = self._convert_to_news_article(entry, rss_url)
                    if article:
                        articles.append(article)
                except Exception as e:
                    logger.error(f"기사 변환 실패: {entry.get('title', 'Unknown')}, {e}")
                    continue
            
            # 날짜순 정렬 (최신이 먼저)
            articles.sort(key=lambda x: self._parse_date(x.date), reverse=True)
            
            logger.info(f"RSS 피드 수집 성공: URL={rss_url}, 기사 수={len(articles)}")
            return articles
            
        except Exception as e:
            logger.error(f"RSS 피드 읽기 실패: URL={rss_url}, 에러={e}")
            return []
    
    def _convert_to_news_article(self, entry, rss_url: str) -> Optional[NewsArticle]:
        """RSS 엔트리를 NewsArticle로 변환"""
        try:
            title = self._clean_html(entry.get('title', ''))
            if not title:
                return None
            
            description = self._clean_html(entry.get('description', ''))
            link = entry.get('link', '')
            
            # 날짜 추출 및 포맷팅
            date = self._format_date(entry)
            
            # 이미지 URL 추출
            image_url = self._extract_image_url(entry, rss_url)
            
            # 카테고리 추출
            category = self._extract_category_from_url(rss_url)
            
            return NewsArticle(
                type=category,
                title=title,
                date=date,
                image=image_url,
                link=link,
                description=description
            )
        except Exception as e:
            logger.error(f"기사 변환 중 오류: {e}")
            return None
    
    def _clean_html(self, html: str) -> str:
        """HTML 태그 제거"""
        if not html:
            return ""
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
            text = soup.get_text()
            # HTML 엔티티 디코딩
            text = text.replace("&quot;", "\"").replace("&amp;", "&")
            text = text.replace("&lt;", "<").replace("&gt;", ">")
            text = text.replace("&nbsp;", " ").strip()
            return text
        except Exception as e:
            logger.warning(f"HTML 정리 실패: {e}")
            return html
    
    def _format_date(self, entry) -> str:
        """날짜 포맷팅 (yyyy.MM.dd)"""
        try:
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                dt = datetime(*entry.published_parsed[:6])
                return dt.strftime("%Y.%m.%d")
            elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                dt = datetime(*entry.updated_parsed[:6])
                return dt.strftime("%Y.%m.%d")
        except Exception as e:
            logger.warning(f"날짜 포맷팅 실패: {e}")
        
        return datetime.now().strftime("%Y.%m.%d")
    
    def _extract_image_url(self, entry, rss_url: str) -> str:
        """이미지 URL 추출 (다양한 전략)"""
        # 1. 연합뉴스 전용 파서
        if 'yonhapnews' in rss_url or 'yna.co.kr' in rss_url:
            image_url = self._extract_yonhap_image(entry)
            if image_url:
                return image_url
        
        # 2. Media 태그 확인
        if hasattr(entry, 'media_content'):
            for media in entry.media_content:
                if media.get('type', '').startswith('image/'):
                    url = media.get('url', '')
                    if url:
                        return self._normalize_image_url(url)
        
        # 3. Description HTML 파싱
        if hasattr(entry, 'description'):
            image_url = self._extract_image_from_html(entry.description)
            if image_url:
                return image_url
        
        # 4. Content 파싱
        if hasattr(entry, 'content'):
            for content in entry.content:
                image_url = self._extract_image_from_html(content.value)
                if image_url:
                    return image_url
        
        # 5. 기본 이미지
        return "https://placehold.co/400x250/000000/FFFFFF?text=RSS"
    
    def _extract_image_from_html(self, html: str) -> Optional[str]:
        """HTML에서 이미지 URL 추출"""
        if not html:
            return None
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
            img = soup.find('img')
            
            if img:
                # src, data-src, data-lazy-src 순서로 확인
                for attr in ['src', 'data-src', 'data-lazy-src']:
                    url = img.get(attr, '')
                    if url:
                        normalized = self._normalize_image_url(url)
                        if self._is_valid_image_url(normalized):
                            return normalized
        except Exception as e:
            logger.debug(f"HTML 이미지 추출 실패: {e}")
        
        return None
    
    def _extract_yonhap_image(self, entry) -> Optional[str]:
        """연합뉴스 전용 이미지 추출"""
        # 프로토콜 없는 URL 패턴: //img.yonhapnews.co.kr/...
        pattern = r'//img\.yonhapnews\.co\.kr/[^"\'\s<>]+'
        
        for field in ['description', 'content']:
            if hasattr(entry, field):
                text = getattr(entry, field)
                if isinstance(text, list):
                    text = ' '.join([str(t) for t in text])
                
                match = re.search(pattern, str(text))
                if match:
                    return 'https:' + match.group()
        
        return None
    
    def _normalize_image_url(self, url: str) -> str:
        """이미지 URL 정규화"""
        if not url:
            return url
        
        url = url.strip()
        
        # 프로토콜 없는 URL 처리 (//로 시작하는 경우)
        if url.startswith("//"):
            return "https:" + url
        
        return url
    
    def _is_valid_image_url(self, url: str) -> bool:
        """이미지 URL 유효성 검증"""
        if not url or not url.strip():
            return False
        
        url_lower = url.strip().lower()
        return url_lower.startswith("http://") or url_lower.startswith("https://")
    
    def _extract_category_from_url(self, rss_url: str) -> str:
        """RSS URL에서 카테고리 추출"""
        category_map = {
            'economy': '경제',
            'politics': '정치',
            'society': '사회',
            'culture': '문화',
            'international': '세계',
            'world': '세계',
            'technology': 'IT/과학',
            'science': '과학',
            'sports': '스포츠',
            'entertainment': '연예'
        }
        
        rss_url_lower = rss_url.lower()
        for key, value in category_map.items():
            if key in rss_url_lower:
                return value
        
        return 'RSS'
    
    def _parse_date(self, date_str: str) -> datetime:
        """날짜 문자열을 datetime으로 파싱"""
        try:
            return datetime.strptime(date_str, "%Y.%m.%d")
        except:
            return datetime.min

