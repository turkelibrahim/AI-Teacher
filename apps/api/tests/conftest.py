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

