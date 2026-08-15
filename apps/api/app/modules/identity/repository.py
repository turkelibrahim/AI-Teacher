from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update
from app.modules.identity.models import User, RefreshToken, AuditLog
import uuid
from typing import Optional

class IdentityRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user_by_email(self, email: str) -> Optional[User]:
        normalized = email.strip().lower()
        result = await self.session.execute(select(User).where(User.email_normalized == normalized))
        return result.scalars().first()

    async def get_user_by_id(self, user_id: uuid.UUID) -> Optional[User]:
        result = await self.session.execute(select(User).where(User.id == user_id))
        return result.scalars().first()

    async def create_user(self, user: User) -> User:
        self.session.add(user)
        await self.session.flush()
        return user

    async def save_refresh_token(self, token: RefreshToken) -> RefreshToken:
        self.session.add(token)
        await self.session.flush()
        return token

    async def get_refresh_token(self, token_hash: str) -> Optional[RefreshToken]:
        result = await self.session.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
        return result.scalars().first()

    async def revoke_refresh_token(self, token_id: uuid.UUID, revoked_at) -> None:
        await self.session.execute(
            update(RefreshToken).where(RefreshToken.id == token_id).values(revoked_at=revoked_at)
        )
        await self.session.flush()

    async def create_audit_log(self, audit_log: AuditLog) -> AuditLog:
        self.session.add(audit_log)
        await self.session.flush()
        return audit_log
