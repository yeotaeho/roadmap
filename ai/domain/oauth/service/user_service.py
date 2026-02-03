from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import logging
from ..model.user import User
from ..repository.user_repository import UserRepository

logger = logging.getLogger(__name__)


class UserService:
    """사용자 관리 서비스"""
    
    def __init__(self, session: AsyncSession):
        self.repository = UserRepository(session)
        self.session = session
    
    async def find_or_create_user(
        self,
        provider: str,
        provider_id: str,
        email: Optional[str] = None,
        name: Optional[str] = None,
        nickname: Optional[str] = None,
        profile_image: Optional[str] = None,
        age: Optional[int] = None,
        pref_domain_json: Optional[dict] = None
    ) -> User:
        """OAuth 제공자 정보로 사용자 찾기 또는 생성"""
        # 기존 사용자 조회 (중복 가능성 대비)
        existing_users = await self.repository.find_by_provider_and_provider_id(
            provider, provider_id
        )
        
        if existing_users:
            # 중복 레코드가 있는 경우 첫 번째 레코드 사용
            user = existing_users[0]
            
            # 중복 레코드가 2개 이상인 경우 나머지 삭제
            if len(existing_users) > 1:
                logger.warn(
                    f"중복 사용자 레코드 발견: provider={provider}, "
                    f"providerId={provider_id}, count={len(existing_users)}"
                )
                
                # 첫 번째 레코드를 제외한 나머지 삭제
                deleted_count = await self.repository.delete_duplicates(
                    provider, provider_id, user.id
                )
                logger.info(f"중복 사용자 레코드 삭제: count={deleted_count}")
            
            # 기존 사용자 정보 업데이트
            user.email = email
            user.name = name
            user.nickname = nickname
            user.profile_image = profile_image
            if age is not None:
                user.age = age
            if pref_domain_json is not None:
                user.pref_domain_json = pref_domain_json
            
            logger.info(
                f"기존 사용자 정보 업데이트: provider={provider}, "
                f"providerId={provider_id}, userId={user.id}"
            )
            
            return await self.repository.save(user)
        else:
            # 신규 사용자 생성
            new_user = User.create(
                provider=provider,
                provider_id=provider_id,
                email=email,
                name=name,
                nickname=nickname,
                profile_image=profile_image,
                age=age,
                pref_domain_json=pref_domain_json
            )
            
            saved_user = await self.repository.save(new_user)
            
            logger.info(
                f"신규 사용자 생성: provider={provider}, "
                f"providerId={provider_id}, userId={saved_user.id}"
            )
            
            return saved_user
    
    async def find_user(self, provider: str, provider_id: str) -> Optional[User]:
        """OAuth 제공자 정보로 사용자 찾기 (생성하지 않음)"""
        users = await self.repository.find_by_provider_and_provider_id(
            provider, provider_id
        )
        return users[0] if users else None
    
    async def find_by_id(self, user_id: int) -> Optional[User]:
        """사용자 ID로 사용자 찾기"""
        return await self.repository.find_by_id(user_id)
    
    async def save(self, user: User) -> User:
        """사용자 정보 업데이트 및 저장"""
        logger.info(f"[UserService] DB 저장 시작 - userId={user.id}, nickname={user.nickname}, name={user.name}")
        saved_user = await self.repository.save(user)
        logger.info(f"[UserService] DB 저장 완료 - userId={saved_user.id}, 저장된 nickname={saved_user.nickname}, 저장된 name={saved_user.name}")
        return saved_user

