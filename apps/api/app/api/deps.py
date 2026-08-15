from fastapi import Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
import uuid
from app.core.config import settings
from app.db.session import get_db_session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.modules.identity.repository import IdentityRepository
from app.modules.organization.repository import OrganizationRepository
from app.modules.identity.models import User
from app.modules.organization.models import OrganizationMember
from app.core.exceptions import UnauthorizedException, ForbiddenException
from typing import Optional

security = HTTPBearer()

def get_identity_repo(session: AsyncSession = Depends(get_db_session)) -> IdentityRepository:
    return IdentityRepository(session)

def get_org_repo(session: AsyncSession = Depends(get_db_session)) -> OrganizationRepository:
    return OrganizationRepository(session)

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    identity_repo: IdentityRepository = Depends(get_identity_repo)
) -> User:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        user_id_str = payload.get("sub")
        if not user_id_str or payload.get("type") != "access":
            raise UnauthorizedException(detail="Invalid token")
        user_id = uuid.UUID(user_id_str)
    except jwt.PyJWTError:
        raise UnauthorizedException(detail="Invalid or expired token")
    except ValueError:
        raise UnauthorizedException(detail="Invalid user ID in token")

    user = await identity_repo.get_user_by_id(user_id)
    if not user or not user.is_active:
        raise UnauthorizedException(detail="User not found or inactive")
    return user

async def get_current_active_user(user: User = Depends(get_current_user)) -> User:
    if not user.is_active:
        raise UnauthorizedException("Inactive user")
    return user

class RequireOrganizationPermission:
    def __init__(self, permission_name: str):
        self.permission_name = permission_name

    async def __call__(
        self, 
        organization_id: uuid.UUID,
        user: User = Depends(get_current_active_user),
        org_repo: OrganizationRepository = Depends(get_org_repo)
    ) -> OrganizationMember:
        member = await org_repo.get_membership_with_roles(user.id, organization_id)
        if not member or member.status != "ACTIVE":
            raise ForbiddenException(detail="Access denied to this organization")
            
        has_permission = False
        is_owner = False
        
        for member_role in member.roles:
            role = member_role.role
            if role.name == "OWNER":
                is_owner = True
                has_permission = True
                break
                
            for rp in role.permissions:
                if rp.permission.name == self.permission_name:
                    has_permission = True
                    break
            
            if has_permission:
                break
                
        if not has_permission:
            raise ForbiddenException(detail=f"Require {self.permission_name} permission")
            
        return member
