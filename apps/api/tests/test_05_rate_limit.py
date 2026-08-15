import pytest
from httpx import AsyncClient
import uuid
from app.core.config import settings

@pytest.fixture
def unique_email():
    return f"test_{uuid.uuid4()}@example.com"

@pytest.mark.asyncio
async def test_19_brute_force_rate_limit_and_reset(client, unique_email):
    # Register user
    await client.post("/api/v1/auth/register", json={"email": unique_email, "password": "Password123!"})
    
    # We use a custom header to spoof IP so this test doesn't interfere with others
    headers = {"X-Forwarded-For": f"192.168.1.{uuid.uuid4().hex[:3]}"}
    
    # Intentionally fail login up to LOGIN_RATE_LIMIT - 1 times
    for i in range(settings.LOGIN_RATE_LIMIT - 1):
        res = await client.post("/api/v1/auth/login", json={"email": unique_email, "password": "WrongPassword!"}, headers=headers)
        assert res.status_code == 401
        
    # The next one should be a successful login which resets the counter
    res_success = await client.post("/api/v1/auth/login", json={"email": unique_email, "password": "Password123!"}, headers=headers)
    assert res_success.status_code == 200
    
    # Now we should have 5 attempts again, so failing 1 time shouldn't be blocked
    res_fail_again = await client.post("/api/v1/auth/login", json={"email": unique_email, "password": "WrongPassword!"}, headers=headers)
    assert res_fail_again.status_code == 401 # Should not be 429
    
    # Now exhaust the limit again
    for i in range(settings.LOGIN_RATE_LIMIT - 1):
        res = await client.post("/api/v1/auth/login", json={"email": unique_email, "password": "WrongPassword!"}, headers=headers)
        assert res.status_code == 401
        
    # Finally, this one must be 429
    res_blocked = await client.post("/api/v1/auth/login", json={"email": unique_email, "password": "WrongPassword!"}, headers=headers)
    assert res_blocked.status_code == 429
