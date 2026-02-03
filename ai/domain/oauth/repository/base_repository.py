from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import NotSupportedError
import logging
from typing import TypeVar, Generic, Callable, Awaitable, Any

logger = logging.getLogger(__name__)

T = TypeVar('T')


class BaseRepository(Generic[T]):
    """
    모든 Repository의 기본 클래스
    
    prepared statement 캐시가 비활성화되어 있으므로
    InvalidCachedStatementError는 발생하지 않아야 합니다.
    하지만 안전장치로 재시도 로직을 유지합니다.
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def _execute_with_retry(
        self, 
        operation: Callable[[], Awaitable[T]], 
        max_retries: int = 2
    ) -> T:
        """
        DB 작업 실행 (재시도 로직 포함)
        
        prepared statement 캐시가 비활성화되어 있으므로
        InvalidCachedStatementError는 발생하지 않아야 하지만,
        다른 DB 에러에 대비한 안전장치로 재시도 로직을 유지합니다.
        
        Args:
            operation: 실행할 비동기 작업
            max_retries: 최대 재시도 횟수
            
        Returns:
            작업 결과
            
        Raises:
            원본 예외 (재시도 실패 시)
        """
        for attempt in range(max_retries):
            try:
                return await operation()
            except Exception as e:
                # InvalidCachedStatementError 관련 에러 확인
                error_str = str(e)
                error_type = type(e).__name__
                
                is_cache_error = (
                    "InvalidCachedStatementError" in error_str or
                    "cached statement plan is invalid" in error_str or
                    "InvalidCachedStatementError" in error_type or
                    isinstance(e, NotSupportedError)
                )
                
                if is_cache_error and attempt < max_retries - 1:
                    # InvalidCachedStatementError 발생 시 재시도
                    logger.warning(
                        f"Prepared statement 캐시 무효화 감지 "
                        f"(시도 {attempt + 1}/{max_retries}), 재시도: {type(e).__name__}"
                    )
                    # 세션 rollback으로 prepared statement 캐시 초기화 시도
                    try:
                        await self.session.rollback()
                    except Exception as rollback_error:
                        logger.warning(f"Rollback 중 에러 발생: {rollback_error}")
                    
                    # 지수 백오프
                    import asyncio
                    await asyncio.sleep(0.1 * (attempt + 1))
                    continue
                else:
                    # 재시도 불가능하거나 다른 에러인 경우
                    if is_cache_error:
                        logger.error(
                            f"Prepared statement 캐시 무효화 에러 - "
                            f"재시도 실패 (시도 {attempt + 1}/{max_retries}): {type(e).__name__}"
                        )
                    raise

