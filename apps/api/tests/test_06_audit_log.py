import pytest
from httpx import AsyncClient
import uuid
from sqlalchemy.future import select
from app.db.session import async_session_maker
from app.modules.identity.models import AuditLog

@pytest.fixture
def unique_email():
    return f"test_{uuid.uuid4()}@example.com"

@pytest.mark.asyncio
async def test_20_audit_log_security(client, unique_email):
    # Register, login, refresh, logout to generate logs
    res = await client.post("/api/v1/auth/register", json={"email": unique_email, "password": "Password123!"})
    rt1 = res.json()["refresh_token"]
    user_id = res.json()["user"]["id"]
    
    await client.post("/api/v1/auth/login", json={"email": unique_email, "password": "WrongPassword!"})
    await client.post("/api/v1/auth/login", json={"email": unique_email, "password": "Password123!"})
    
    res_refresh = await client.post("/api/v1/auth/refresh", json={"refresh_token": rt1})
    rt2 = res_refresh.json()["refresh_token"]
    
    await client.post("/api/v1/auth/logout", json={"refresh_token": rt2})
    
    # Intentionally reuse token
    await client.post("/api/v1/auth/refresh", json={"refresh_token": rt2})
    
    # Check logs
    async with async_session_maker() as session:
        result = await session.execute(select(AuditLog).where(AuditLog.user_id == uuid.UUID(user_id)))
        logs = result.scalars().all()
        
        events = [log.event_type for log in logs]
        assert "USER_REGISTERED" in events
        assert "USER_LOGIN_SUCCESS" in events
        assert "USER_LOGIN_FAILED" in events
        assert "REFRESH_TOKEN_ROTATED" in events
        assert "USER_LOGOUT" in events
        assert "REFRESH_TOKEN_REUSED" in events
        
        # Verify no sensitive info
        for log in logs:
            if log.metadata_:
                assert "password" not in str(log.metadata_).lower()
                assert "access_token" not in str(log.metadata_).lower()
                assert rt1 not in str(log.metadata_)
                assert rt2 not in str(log.metadata_)
                assert "authorization" not in str(log.metadata_).lower()
                assert "bearer" not in str(log.metadata_).lower()
