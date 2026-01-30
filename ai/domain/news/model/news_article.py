from pydantic import BaseModel
from typing import Optional


class NewsArticle(BaseModel):
    """뉴스 기사 모델"""
    type: str
    title: str
    date: str
    image: str
    link: str
    description: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "type": "경제",
                "title": "뉴스 제목",
                "date": "2025.01.30",
                "image": "https://example.com/image.jpg",
                "link": "https://example.com/news/123",
                "description": "뉴스 설명"
            }
        }

