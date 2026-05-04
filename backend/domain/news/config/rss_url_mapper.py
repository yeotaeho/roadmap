from typing import List, Dict
import yaml
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class RssUrlMapper:
    """RSS URL 매핑 관리 클래스"""
    
    # 카테고리명 매핑 (한글 -> 영문 키)
    CATEGORY_MAPPING = {
        "경제": "economy",
        "정치": "politics",
        "사회": "society",
        "문화": "culture",
        "세계": "world",
        "IT/과학": "it-science",
        "IT": "it-science",
        "과학": "it-science",
        "스포츠": "sports",
        "연예": "entertainment",
        "엔터테인먼트": "entertainment",
        "개발": "it-science",
        "이슈": "society",
        "기술": "it-science"
    }
    
    def __init__(self, rss_config_path: str = None):
        """
        RSS URL 매퍼 초기화
        
        Args:
            rss_config_path: RSS 설정 파일 경로 (기본값: ai/domain/news/config/rss-urls.yml)
        """
        if rss_config_path is None:
            # 기본 경로: ai/domain/news/config/rss-urls.yml
            # __file__ = ai/domain/news/config/rss_url_mapper.py
            # parent = ai/domain/news/config/
            rss_config_path = (
                Path(__file__).parent 
                / "rss-urls.yml"
            )
        
        self.rss_config_path = Path(rss_config_path)
        self.rss_config = self._load_config()
        self.categories = self._extract_categories()
    
    def _load_config(self) -> Dict:
        """YAML 설정 파일 로드"""
        try:
            with open(self.rss_config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                logger.info(f"RSS 설정 파일 로드 성공: {self.rss_config_path}")
                return config
        except FileNotFoundError:
            logger.error(f"RSS 설정 파일을 찾을 수 없습니다: {self.rss_config_path}")
            return {}
        except Exception as e:
            logger.error(f"RSS 설정 파일 로드 실패: {e}")
            return {}
    
    def _extract_categories(self) -> List[str]:
        """설정에서 카테고리 목록 추출"""
        sources = self.rss_config.get('rss', {}).get('sources', {})
        return list(sources.keys())
    
    def is_category(self, query: str) -> bool:
        """
        쿼리가 정의된 카테고리인지 확인
        
        Args:
            query: 확인할 쿼리 문자열
            
        Returns:
            카테고리인지 여부
        """
        # 한글 카테고리명 확인
        if query in self.CATEGORY_MAPPING:
            return True
        
        # 영문 키 확인
        category_key = self.CATEGORY_MAPPING.get(query, query.lower())
        if category_key in self.categories:
            return True
        
        # 소문자로 변환하여 확인
        if query.lower() in [cat.lower() for cat in self.categories]:
            return True
        
        return False
    
    def get_rss_urls_by_category(self, category: str) -> List[str]:
        """
        카테고리별 RSS URL 목록 반환
        
        Args:
            category: 카테고리명 (한글 또는 영문)
            
        Returns:
            RSS URL 목록
        """
        # 한글 카테고리명을 영문 키로 변환
        category_key = self.CATEGORY_MAPPING.get(category, category.lower())
        
        # 소문자로 변환하여 매칭 시도
        sources = self.rss_config.get('rss', {}).get('sources', {})
        
        # 정확한 키 매칭 시도
        if category_key in sources:
            category_sources = sources[category_key]
        else:
            # 대소문자 무시 매칭
            category_sources = None
            for key, value in sources.items():
                if key.lower() == category_key.lower():
                    category_sources = value
                    break
        
        if not category_sources:
            logger.warning(f"카테고리에 해당하는 RSS URL이 없습니다: category={category}")
            return []
        
        # enabled가 true인 것만 필터링
        rss_urls = [
            source['url']
            for source in category_sources
            if source.get('enabled', True)
        ]
        
        logger.info(f"카테고리 '{category}'의 RSS URL 개수: {len(rss_urls)}")
        return rss_urls
    
    def get_all_categories(self) -> List[str]:
        """모든 카테고리 목록 반환"""
        return list(self.CATEGORY_MAPPING.keys())

