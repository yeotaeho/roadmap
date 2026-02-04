"""
User Domain Database Base
기존 oauth 도메인의 Base를 재사용하여 동일한 데이터베이스 연결 사용
"""
from domain.oauth.base.database import Base, get_db, AsyncSessionLocal

__all__ = ['Base', 'get_db', 'AsyncSessionLocal']
