from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db_session
from app.modules.identity.schemas import UserCreate, UserLogin, TokenResponse, RefreshTokenRequest, UserResponse, AuthResponse
from app.modules.identity.service import IdentityService
from app.modules.identity.repository import IdentityRepository
from app.modules.organization.repository import OrganizationRepository
from app.api.deps import get_current_active_user
from app.modules.identity.models import User
from app.core.exceptions import TooManyRequestsException
from app.core.redis import get_redis
from app.core.config import settings
import time

router = APIRouter()

def get_identity_service(session: AsyncSession = Depends(get_db_session)) -> IdentityService:
    return IdentityService(IdentityRepository(session), OrganizationRepository(session))

async def check_rate_limit(request: Request):
    client_ip = request.client.host if request.client else "unknown"
    redis = await get_redis()
    key = f"rate_limit:login:{client_ip}"
    
    current = await redis.get(key)
    if current and int(current) >= settings.LOGIN_RATE_LIMIT:
        raise TooManyRequestsException(detail="Too many login attempts. Please try again later.")
    
    pipe = redis.pipeline()
    pipe.incr(key)
    if not current:
        pipe.expire(key, settings.LOGIN_RATE_LIMIT_WINDOW)
    await pipe.execute()

@router.post("/register", response_model=AuthResponse)
async def register(
    data: UserCreate, 
    service: IdentityService = Depends(get_identity_service)
):
    user, access, refresh = await service.register_user(data.email, data.password, data.first_name, data.last_name)
    return AuthResponse(access_token=access, refresh_token=refresh, user=user)

@router.post("/login", response_model=TokenResponse)
async def login(
    request: Request,
    data: UserLogin, 
    service: IdentityService = Depends(get_identity_service),
    _: None = Depends(check_rate_limit)
):
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    
    access, refresh = await service.login(data.email, data.password, ip_address, user_agent)
    
    # Reset rate limit on success
    redis = await get_redis()
    await redis.delete(f"rate_limit:login:{ip_address}")
    
    return TokenResponse(access_token=access, refresh_token=refresh)

@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: Request,
    data: RefreshTokenRequest,
    service: IdentityService = Depends(get_identity_service)
):
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    
    access, refresh = await service.refresh_token(data.refresh_token, ip_address, user_agent)
    return TokenResponse(access_token=access, refresh_token=refresh)

@router.post("/logout")
async def logout(
    data: RefreshTokenRequest,
    service: IdentityService = Depends(get_identity_service)
):
    await service.logout(data.refresh_token)
    return {"success": True}

@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_active_user)):
    return user
