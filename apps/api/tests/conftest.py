import pytest
import asyncio
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.redis import get_redis

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest_asyncio.fixture(scope="session")
async def client():
    from app.core.storage import get_storage
    from app.core.config import settings
    storage = await get_storage()
    await storage.initialize(settings.RESOURCE_BUCKET_NAME)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

@pytest_asyncio.fixture(autouse=True)
async def clear_redis():
    redis = await get_redis()
    await redis.flushdb()



from app.db.session import async_session_maker
from sqlalchemy.ext.asyncio import AsyncSession
import pytest_asyncio

@pytest_asyncio.fixture(scope="function")
async def db() -> AsyncSession:
    async with async_session_maker() as session:
        yield session


import uuid

@pytest.fixture
def unique_email():
    return f"test_{uuid.uuid4()}@example.com"

@pytest.fixture
def unique_email2():
    return f"test_{uuid.uuid4()}@example.com"

@pytest_asyncio.fixture
async def setup_tenants(client, unique_email, unique_email2):
    res_a = await client.post("/api/v1/auth/register", json={"email": unique_email, "password": "Password123!"})
    token_a = res_a.json()["access_token"]
    user_a_id = res_a.json()["user"]["id"]
    
    res_b = await client.post("/api/v1/auth/register", json={"email": unique_email2, "password": "Password123!"})
    token_b = res_b.json()["access_token"]
    
    orgs_a = await client.get("/api/v1/organizations", headers={"Authorization": f"Bearer {token_a}"})
    org_a_id = orgs_a.json()[0]["id"]
    
    orgs_b = await client.get("/api/v1/organizations", headers={"Authorization": f"Bearer {token_b}"})
    org_b_id = orgs_b.json()[0]["id"]
    
    return token_a, user_a_id, org_a_id, token_b, org_b_id
