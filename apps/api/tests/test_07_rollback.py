import pytest
from httpx import AsyncClient
import uuid
from sqlalchemy.future import select
from app.db.session import async_session_maker
from app.modules.identity.models import User
from unittest.mock import patch
from app.modules.organization.repository import OrganizationRepository

@pytest.fixture
def unique_email():
    return f"test_{uuid.uuid4()}@example.com"

@pytest.mark.asyncio
async def test_23_registration_rollback(client, unique_email):
    # Patch org repo to simulate failure
    original_create = OrganizationRepository.create_organization
    
    async def mocked_create(*args, **kwargs):
        raise ValueError("Simulated DB failure")

    with patch.object(OrganizationRepository, 'create_organization', new=mocked_create):
        try:
            await client.post("/api/v1/auth/register", json={"email": unique_email, "password": "Password123!"})
        except ValueError:
            pass
        
    async with async_session_maker() as session:
        result = await session.execute(select(User).where(User.email_normalized == unique_email.lower()))
        user = result.scalars().first()
        assert user is None

