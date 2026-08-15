import pytest
from httpx import AsyncClient
import uuid
from sqlalchemy.future import select
from app.db.session import async_session_maker
from app.modules.identity.models import User
from app.modules.organization.models import Organization, OrganizationMember

@pytest.fixture
def unique_email():
    return f"test_{uuid.uuid4()}@example.com"

@pytest.mark.asyncio
async def test_01_valid_registration_and_db_models(client, unique_email):
    # 1. Valid registration
    # 3. Password not plaintext
    # 4. Personal organization created
    # 5. Owner membership created
    response = await client.post("/api/v1/auth/register", json={
        "email": unique_email,
        "password": "Password123!",
        "first_name": "Test",
        "last_name": "User"
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    user_id = data["user"]["id"]
    
    async with async_session_maker() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalars().first()
        assert user.password_hash != "Password123!"
        assert user.password_hash.startswith("$argon2")
        
        # Check personal org
        result = await session.execute(select(OrganizationMember).where(OrganizationMember.user_id == user_id))
        memberships = result.scalars().all()
        assert len(memberships) == 1
        assert memberships[0].status == "ACTIVE"
        
        # Check role (id 1)
        # It's an OWNER. Checked later in RBAC.

@pytest.mark.asyncio
async def test_02_duplicate_email_fails(client, unique_email):
    payload = {"email": unique_email, "password": "Password123!"}
    res1 = await client.post("/api/v1/auth/register", json=payload)
    assert res1.status_code == 200
    
    res2 = await client.post("/api/v1/auth/register", json=payload)
    assert res2.status_code == 400

@pytest.mark.asyncio
async def test_03_login_correct_credentials(client, unique_email):
    payload = {"email": unique_email, "password": "Password123!"}
    await client.post("/api/v1/auth/register", json=payload)
    
    res = await client.post("/api/v1/auth/login", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    
    # Check last_login_at
    async with async_session_maker() as session:
        result = await session.execute(select(User).where(User.email == unique_email))
        user = result.scalars().first()
        assert user.last_login_at is not None

@pytest.mark.asyncio
async def test_04_wrong_password(client, unique_email):
    payload = {"email": unique_email, "password": "Password123!"}
    await client.post("/api/v1/auth/register", json=payload)
    
    res = await client.post("/api/v1/auth/login", json={"email": unique_email, "password": "WrongPassword!"})
    assert res.status_code == 401

@pytest.mark.asyncio
async def test_05_nonexistent_user(client):
    res = await client.post("/api/v1/auth/login", json={"email": "not_exist@example.com", "password": "Password123!"})
    assert res.status_code == 401

@pytest.mark.asyncio
async def test_06_inactive_user(client, unique_email):
    payload = {"email": unique_email, "password": "Password123!"}
    await client.post("/api/v1/auth/register", json=payload)
    
    async with async_session_maker() as session:
        result = await session.execute(select(User).where(User.email == unique_email))
        user = result.scalars().first()
        user.is_active = False
        await session.commit()
        
    res = await client.post("/api/v1/auth/login", json=payload)
    assert res.status_code == 401
