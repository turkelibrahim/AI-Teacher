import pytest
from httpx import AsyncClient
import uuid
from app.core.config import settings

@pytest.fixture
def unique_email():
    return f"test_{uuid.uuid4()}@example.com"

@pytest.mark.asyncio
async def test_19_brute_force_rate_limit(client, unique_email):
    # 31 brute-force threshold enforced
    # Create user
    await client.post("/api/v1/auth/register", json={"email": unique_email, "password": "Password123!"})
    
    # Intentionally fail login up to LOGIN_RATE_LIMIT times
    for i in range(settings.LOGIN_RATE_LIMIT):
        res = await client.post("/api/v1/auth/login", json={"email": unique_email, "password": "WrongPassword!"})
        assert res.status_code == 401
        
    # The next one should be 429
    res_blocked = await client.post("/api/v1/auth/login", json={"email": unique_email, "password": "WrongPassword!"})
    assert res_blocked.status_code == 429
    
    # Check that it resets on success? Wait, we can't test success here because it's blocked by IP.
    # To test success reset, we would need to mock IP or clear redis. We'll rely on redis flush in conftest.
