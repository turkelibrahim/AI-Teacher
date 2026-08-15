from datetime import timezone
import pytest
from httpx import AsyncClient
import uuid
import jwt
from datetime import datetime, timedelta
from app.core.config import settings
from app.db.session import async_session_maker
from sqlalchemy.future import select
from app.modules.identity.models import RefreshToken
import time

@pytest.fixture
def unique_email():
    return f"test_{uuid.uuid4()}@example.com"

@pytest.mark.asyncio
async def test_07_jwt_claims_and_valid_access(client, unique_email):
    # 10 valid access
    payload = {"email": unique_email, "password": "Password123!"}
    res = await client.post("/api/v1/auth/register", json=payload)
    token = res.json()["access_token"]
    
    me_res = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    
    # decode and verify claims
    decoded = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    assert "iat" in decoded
    assert "exp" in decoded
    assert "sub" in decoded
    assert "type" in decoded
    assert "jti" in decoded
    assert decoded["type"] == "access"

@pytest.mark.asyncio
async def test_08_expired_token(client):
    # 11 expired token
    expire = datetime.now(timezone.utc) - timedelta(minutes=5)
    to_encode = {"exp": expire, "iat": datetime.now(timezone.utc), "sub": str(uuid.uuid4()), "type": "access", "jti": "123"}
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    
    me_res = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {encoded_jwt}"})
    assert me_res.status_code == 401

@pytest.mark.asyncio
async def test_09_malformed_token(client):
    # 12 malformed token
    me_res = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer completely-fake-token"})
    assert me_res.status_code == 401

@pytest.mark.asyncio
async def test_10_wrong_token_type(client):
    # 13 wrong token type
    expire = datetime.now(timezone.utc) + timedelta(minutes=5)
    to_encode = {"exp": expire, "iat": datetime.now(timezone.utc), "sub": str(uuid.uuid4()), "type": "refresh", "jti": "123"}
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    
    me_res = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {encoded_jwt}"})
    assert me_res.status_code == 401

@pytest.mark.asyncio
async def test_11_refresh_token_rotation_and_revocation(client, unique_email):
    # 14 valid refresh
    # 15 old token revoked after rotation
    payload = {"email": unique_email, "password": "Password123!"}
    res = await client.post("/api/v1/auth/register", json=payload)
    rt1 = res.json()["refresh_token"]
    
    # refresh it
    refresh_res = await client.post("/api/v1/auth/refresh", json={"refresh_token": rt1})
    assert refresh_res.status_code == 200
    rt2 = refresh_res.json()["refresh_token"]
    assert rt1 != rt2
    
    # Check old token in DB
    async with async_session_maker() as session:
        import hashlib
        h = hashlib.sha256(rt1.encode()).hexdigest()
        result = await session.execute(select(RefreshToken).where(RefreshToken.token_hash == h))
        rt1_db = result.scalars().first()
        
        assert rt1_db.revoked_at is not None
        assert rt1_db.replaced_by_token_id is not None
        
        h2 = hashlib.sha256(rt2.encode()).hexdigest()
        result = await session.execute(select(RefreshToken).where(RefreshToken.token_hash == h2))
        rt2_db = result.scalars().first()
        assert rt1_db.replaced_by_token_id == rt2_db.id

@pytest.mark.asyncio
async def test_12_old_token_reuse_denied(client, unique_email):
    # 16 old token reuse denied
    payload = {"email": unique_email, "password": "Password123!"}
    res = await client.post("/api/v1/auth/register", json=payload)
    rt1 = res.json()["refresh_token"]
    
    refresh_res1 = await client.post("/api/v1/auth/refresh", json={"refresh_token": rt1})
    assert refresh_res1.status_code == 200
    
    refresh_res2 = await client.post("/api/v1/auth/refresh", json={"refresh_token": rt1})
    assert refresh_res2.status_code == 401

@pytest.mark.asyncio
async def test_13_logout_revokes_refresh(client, unique_email):
    # 19 logout revokes refresh
    # 17 explicitly revoked refresh denied
    payload = {"email": unique_email, "password": "Password123!"}
    res = await client.post("/api/v1/auth/register", json=payload)
    rt = res.json()["refresh_token"]
    
    logout_res = await client.post("/api/v1/auth/logout", json={"refresh_token": rt})
    assert logout_res.status_code == 200
    
    # 20 revoked refresh cannot refresh
    refresh_res = await client.post("/api/v1/auth/refresh", json={"refresh_token": rt})
    assert refresh_res.status_code == 401

@pytest.mark.asyncio
async def test_14_expired_refresh_denied(client, unique_email):
    # 18 expired refresh denied
    payload = {"email": unique_email, "password": "Password123!"}
    res = await client.post("/api/v1/auth/register", json=payload)
    rt = res.json()["refresh_token"]
    
    async with async_session_maker() as session:
        import hashlib
        h = hashlib.sha256(rt.encode()).hexdigest()
        result = await session.execute(select(RefreshToken).where(RefreshToken.token_hash == h))
        rt_db = result.scalars().first()
        rt_db.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        await session.commit()
        
    refresh_res = await client.post("/api/v1/auth/refresh", json={"refresh_token": rt})
    assert refresh_res.status_code == 401


@pytest.mark.asyncio
async def test_24_unknown_user_jwt(client):
    expire = datetime.now(timezone.utc) + timedelta(minutes=5)
    # Valid UUID but unknown user
    to_encode = {"exp": expire, "iat": datetime.now(timezone.utc), "sub": str(uuid.uuid4()), "type": "access", "jti": "123"}
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    
    me_res = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {encoded_jwt}"})
    assert me_res.status_code == 401
