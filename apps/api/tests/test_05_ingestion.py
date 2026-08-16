import pytest
from httpx import AsyncClient
import uuid
import io
import asyncio
from app.db.session import async_session_maker
from app.modules.organization.models import Organization, OrganizationMember
from app.modules.identity.models import User
from app.modules.resource.models import Resource
from sqlalchemy.future import select

@pytest.fixture
def unique_email():
    return f"test_ingest_{uuid.uuid4()}@example.com"

async def setup_user_and_org(client, email):
    # Register
    res = await client.post("/api/v1/auth/register", json={
        "email": email,
        "password": "Password123!",
        "first_name": "Test",
        "last_name": "Ingest"
    })
    
    # Login
    token = res.json()['access_token']
    
    async with async_session_maker() as session:
        user_result = await session.execute(select(User).filter(User.email == email))
        user = user_result.scalars().first()
        org = Organization(name=f"Ingest Org {uuid.uuid4()}", slug=f"ingest-{uuid.uuid4()}")
        session.add(org)
        await session.commit()
        from app.modules.identity.models import Role
        from app.modules.organization.models import MemberRole
        member = OrganizationMember(organization_id=org.id, user_id=user.id, status="ACTIVE")
        session.add(member)
        await session.commit()
        role_result = await session.execute(select(Role).filter(Role.name == "OWNER"))
        owner_role = role_result.scalars().first()
        session.add(MemberRole(member_id=member.id, role_id=owner_role.id))
        session.add(member)
        await session.commit()
        org_id = str(org.id)
    return token, org_id

@pytest.mark.asyncio
async def test_ingestion_pipeline_txt(client: AsyncClient, unique_email):
    token, org_id = await setup_user_and_org(client, unique_email)
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Upload TXT file
    file_content = b"Hello world! This is a test document.\nIt has multiple lines.\n"
    files = {"file": ("test.txt", io.BytesIO(file_content), "text/plain")}
    res = await client.post(f"/api/v1/organizations/{org_id}/resources", files=files, headers=headers)
    assert res.status_code in [200, 201], res.text
    resource_id = res.json()['id']
    
    # 2. Start Ingestion
    res = await client.post(f"/api/v1/organizations/{org_id}/resources/{resource_id}/ingestions", json={}, headers=headers)
    assert res.status_code == 202, res.text
    job_id = res.json()['id']
    assert res.json()["status"] == "QUEUED"
    
    # 3. Wait for Celery worker to process
    # Since we are using an actual Celery worker in the test environment, we poll until completed
    # Alternatively we can poll the API
    max_retries = 20
    status = "QUEUED"
    for _ in range(max_retries):
        res = await client.get(f"/api/v1/organizations/{org_id}/resources/{resource_id}/ingestions/{job_id}", headers=headers)
        assert res.status_code == 200, res.text
        status = res.json()["status"]
        if status in ["COMPLETED", "FAILED"]:
            break
        await asyncio.sleep(1)
        
    assert status == "COMPLETED", f"Status is {status}"
    
    # 4. Check document
    res = await client.get(f"/api/v1/organizations/{org_id}/resources/{resource_id}/document", headers=headers)
    assert res.status_code == 200, res.text
    doc = res.json()
    assert doc["total_pages"] == 1
    assert "Hello world!" in doc["plain_text"]
    
    # 5. Check pages
    res = await client.get(f"/api/v1/organizations/{org_id}/resources/{resource_id}/pages", headers=headers)
    assert res.status_code == 200, res.text
    pages = res.json()
    assert pages["total"] == 1
    assert len(pages["items"]) == 1
    assert pages["items"][0]["page_number"] == 1
    assert "Hello world!" in pages["items"][0]["text"]









