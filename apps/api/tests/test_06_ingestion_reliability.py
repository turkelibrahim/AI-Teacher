"""
Phase 4 ingestion reliability, RBAC, and integration tests.
All tests use OWNER-created org to avoid MEMBER upload-permission issues.
"""
import pytest
import asyncio
import uuid

from httpx import AsyncClient
from sqlalchemy.future import select

from app.db.session import async_session_maker
from app.modules.organization.models import Organization, OrganizationMember
from app.modules.identity.models import User, Role, AuditLog
from app.modules.ingestion.models import ResourceIngestionJob, ResourceDocument, ResourcePage


async def _register_and_login(client, email, password="Password123!"):
    res = await client.post("/api/v1/auth/register", json={
        "email": email, "password": password, "first_name": "T", "last_name": "I"
    })
    assert res.status_code in (200, 201), f"Register failed: {res.text}"
    return res.json()["access_token"]


async def _get_user_id(email):
    async with async_session_maker() as session:
        result = await session.execute(select(User).where(User.email == email))
        return result.scalars().first().id


async def _add_member(org_id, user_id, role_name):
    async with async_session_maker() as session:
        from app.modules.organization.models import MemberRole
        member = OrganizationMember(organization_id=org_id, user_id=user_id, status="ACTIVE")
        session.add(member)
        await session.flush()
        role = (await session.execute(select(Role).where(Role.name == role_name))).scalars().first()
        session.add(MemberRole(member_id=member.id, role_id=role.id))
        await session.commit()


async def _setup_owner_org(client, email):
    token = await _register_and_login(client, email)
    user_id = await _get_user_id(email)
    async with async_session_maker() as session:
        from app.modules.organization.models import MemberRole
        org = Organization(name=f"Org {uuid.uuid4()}", slug=f"org-{uuid.uuid4()}")
        session.add(org)
        await session.flush()
        member = OrganizationMember(organization_id=org.id, user_id=user_id, status="ACTIVE")
        session.add(member)
        await session.flush()
        role = (await session.execute(select(Role).where(Role.name == "OWNER"))).scalars().first()
        session.add(MemberRole(member_id=member.id, role_id=role.id))
        await session.commit()
        org_id = org.id
    return token, org_id


async def _upload(client, token, org_id, content=b"Hello", filename="test.txt"):
    res = await client.post(
        f"/api/v1/organizations/{org_id}/resources",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": (filename, content, "text/plain")}
    )
    assert res.status_code == 200, f"Upload failed: {res.text}"
    return res.json()["id"]


async def _ingest(client, token, org_id, resource_id, force=False):
    return await client.post(
        f"/api/v1/organizations/{org_id}/resources/{resource_id}/ingestions",
        headers={"Authorization": f"Bearer {token}"},
        json={"force": force}
    )


async def _poll(client, token, org_id, resource_id, job_id, timeout=30):
    headers = {"Authorization": f"Bearer {token}"}
    for _ in range(timeout // 2):
        res = await client.get(
            f"/api/v1/organizations/{org_id}/resources/{resource_id}/ingestions/{job_id}",
            headers=headers
        )
        assert res.status_code == 200, res.text
        if res.json()["status"] in ("COMPLETED", "FAILED"):
            return res.json()
        await asyncio.sleep(2)
    return res.json()


@pytest.fixture
def unique_email():
    return f"test_{uuid.uuid4()}@example.com"


@pytest.mark.asyncio
async def test_rbac_owner_admin_instructor_allow(client: AsyncClient, unique_email):
    owner_token, org_id = await _setup_owner_org(client, f"owner_{unique_email}")
    resource_id = await _upload(client, owner_token, org_id)

    r = await _ingest(client, owner_token, org_id, resource_id)
    assert r.status_code == 202, f"OWNER must ALLOW: {r.text}"

    admin_token = await _register_and_login(client, f"admin_{unique_email}")
    await _add_member(org_id, await _get_user_id(f"admin_{unique_email}"), "ADMIN")
    r = await _ingest(client, admin_token, org_id, resource_id, force=True)
    assert r.status_code == 202, f"ADMIN must ALLOW: {r.text}"

    instr_token = await _register_and_login(client, f"instr_{unique_email}")
    await _add_member(org_id, await _get_user_id(f"instr_{unique_email}"), "INSTRUCTOR")
    r = await _ingest(client, instr_token, org_id, resource_id, force=True)
    assert r.status_code == 202, f"INSTRUCTOR must ALLOW: {r.text}"


@pytest.mark.asyncio
async def test_rbac_member_denied(client: AsyncClient, unique_email):
    owner_token, org_id = await _setup_owner_org(client, f"owner_{unique_email}")
    resource_id = await _upload(client, owner_token, org_id)

    member_token = await _register_and_login(client, f"member_{unique_email}")
    await _add_member(org_id, await _get_user_id(f"member_{unique_email}"), "MEMBER")

    r = await _ingest(client, member_token, org_id, resource_id)
    assert r.status_code == 403, f"MEMBER must be DENIED: {r.text}"


@pytest.mark.asyncio
async def test_rbac_member_can_read(client: AsyncClient, unique_email):
    owner_token, org_id = await _setup_owner_org(client, f"owner_{unique_email}")
    resource_id = await _upload(client, owner_token, org_id)
    r = await _ingest(client, owner_token, org_id, resource_id)
    assert r.status_code == 202
    job_id = r.json()["id"]

    member_token = await _register_and_login(client, f"member_{unique_email}")
    await _add_member(org_id, await _get_user_id(f"member_{unique_email}"), "MEMBER")

    h = {"Authorization": f"Bearer {member_token}"}
    list_r = await client.get(f"/api/v1/organizations/{org_id}/resources/{resource_id}/ingestions", headers=h)
    assert list_r.status_code == 200, f"MEMBER read list must ALLOW: {list_r.text}"
    get_r = await client.get(f"/api/v1/organizations/{org_id}/resources/{resource_id}/ingestions/{job_id}", headers=h)
    assert get_r.status_code == 200, f"MEMBER get job must ALLOW: {get_r.text}"


@pytest.mark.asyncio
async def test_tenant_isolation(client: AsyncClient, unique_email):
    token_a, org_a = await _setup_owner_org(client, f"owner_a_{unique_email}")
    token_b, org_b = await _setup_owner_org(client, f"owner_b_{unique_email}")
    resource_b = await _upload(client, token_b, org_b)

    r = await _ingest(client, token_a, org_a, resource_b)
    assert r.status_code in (403, 404), f"Cross-tenant must be denied: {r.text}"


@pytest.mark.asyncio
async def test_worker_integration_txt(client: AsyncClient, unique_email):
    token, org_id = await _setup_owner_org(client, unique_email)
    resource_id = await _upload(
        client, token, org_id,
        content=b"Integration test content line 1.\nLine 2.",
        filename="integration.txt"
    )
    r = await _ingest(client, token, org_id, resource_id)
    assert r.status_code == 202
    job_id = r.json()["id"]

    final = await _poll(client, token, org_id, resource_id, job_id, timeout=30)
    assert final["status"] == "COMPLETED", f"Worker failed: {final}"
    assert final["page_count"] == 1

    doc = await client.get(
        f"/api/v1/organizations/{org_id}/resources/{resource_id}/document",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert doc.status_code == 200
    assert "Integration test content" in doc.json()["plain_text"]


@pytest.mark.asyncio
async def test_idempotency(client: AsyncClient, unique_email):
    token, org_id = await _setup_owner_org(client, unique_email)
    resource_id = await _upload(client, token, org_id)
    r1 = await _ingest(client, token, org_id, resource_id)
    r2 = await _ingest(client, token, org_id, resource_id)
    assert r1.status_code == 202 and r2.status_code == 202
    assert r1.json()["id"] == r2.json()["id"], "Idempotency broken"


@pytest.mark.asyncio
async def test_reingestion_force(client: AsyncClient, unique_email):
    token, org_id = await _setup_owner_org(client, unique_email)
    resource_id = await _upload(client, token, org_id, b"v1")

    r1 = await _ingest(client, token, org_id, resource_id)
    assert r1.status_code == 202
    final1 = await _poll(client, token, org_id, resource_id, r1.json()["id"], timeout=30)
    assert final1["status"] == "COMPLETED"

    r2 = await _ingest(client, token, org_id, resource_id, force=True)
    assert r2.status_code == 202
    assert r2.json()["id"] != r1.json()["id"], "force=True must create new job"

    final2 = await _poll(client, token, org_id, resource_id, r2.json()["id"], timeout=30)
    assert final2["status"] == "COMPLETED"

    doc = await client.get(
        f"/api/v1/organizations/{org_id}/resources/{resource_id}/document",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert doc.json()["ingestion_job_id"] == r2.json()["id"]


@pytest.mark.asyncio
async def test_duplicate_execution_single_claim(client: AsyncClient, unique_email):
    token, org_id = await _setup_owner_org(client, unique_email)
    resource_id = await _upload(client, token, org_id, b"Dup test")

    from app.modules.ingestion.repository import IngestionRepository
    from app.modules.ingestion.models import ResourceIngestionJob
    import datetime

    # Directly create QUEUED job in DB to avoid Celery worker
    job_id = uuid.uuid4()
    async with async_session_maker() as s:
        # Get actual user id
        user_id = await _get_user_id(unique_email)
        job = ResourceIngestionJob(
            id=job_id,
            organization_id=org_id,
            resource_id=resource_id,
            requested_by_user_id=user_id,
            status="QUEUED"
        )
        s.add(job)
        await s.commit()

    # Now we have a QUEUED job that the worker doesn't know about.
    async with async_session_maker() as s1:
        c1 = await IngestionRepository(s1).claim_job(job_id)
        await s1.commit()
        
    async with async_session_maker() as s2:
        c2 = await IngestionRepository(s2).claim_job(job_id)
        await s2.commit()

    claims = sum(1 for c in [c1, c2] if c is not None)
    assert claims == 1, f"Exactly 1 claim expected, got {claims}"

    # Verify status is PROCESSING and no ResourceDocument is created
    async with async_session_maker() as s:
        job = await IngestionRepository(s).get_job_by_id_only(job_id)
        assert job.status == "PROCESSING"
        docs = (await s.execute(
            select(ResourceDocument).where(ResourceDocument.ingestion_job_id == job_id)
        )).scalars().all()
    assert len(docs) == 0, f"No documents expected, got {len(docs)}"

@pytest.mark.asyncio
async def test_transient_retry_success(client: AsyncClient, unique_email):
    token, org_id = await _setup_owner_org(client, unique_email)
    resource_id = await _upload(client, token, org_id, b"Retry text")

    from app.core.storage import ObjectStorage
    storage = ObjectStorage()
    
    async with async_session_maker() as session:
        from app.modules.resource.repository import ResourceRepository
        resource = await ResourceRepository(session).get_by_id(org_id, resource_id)
        bucket = resource.storage_bucket
        key = resource.storage_key
        
    # Get the object content to put it back later
    response = await storage.get(key, bucket_name=bucket)
    content = b""
    for chunk in response.stream(32*1024):
        content += chunk
    response.close()
    response.release_conn()
    
    # Delete the object to trigger transient error
    await storage.delete(key, bucket_name=bucket)
    
    r = await _ingest(client, token, org_id, resource_id)
    assert r.status_code == 202
    job_id = r.json()["id"]

    # Wait for the first failure to trigger retry
    await asyncio.sleep(4)
    
    from app.modules.ingestion.repository import IngestionRepository
    async with async_session_maker() as session:
        job = await IngestionRepository(session).get_job_by_id_only(uuid.UUID(job_id))
        assert job.status in ("QUEUED", "PROCESSING"), f"Expected job to be retryable (QUEUED or PROCESSING), got {job.status}"

    # Restore the object in MinIO so the retry succeeds
    import io
    await storage.put(key, io.BytesIO(content), len(content), bucket_name=bucket)

    # Poll for completion (retry happens in ~10s)
    final = await _poll(client, token, org_id, resource_id, job_id, timeout=30)
    assert final["status"] == "COMPLETED"


@pytest.mark.asyncio
async def test_audit_logs(client: AsyncClient, unique_email):
    token, org_id = await _setup_owner_org(client, unique_email)
    resource_id = await _upload(client, token, org_id, b"Audit content")
    r = await _ingest(client, token, org_id, resource_id)
    assert r.status_code == 202
    job_id = r.json()["id"]

    final = await _poll(client, token, org_id, resource_id, job_id, timeout=30)
    assert final["status"] == "COMPLETED"

    async with async_session_maker() as s:
        logs = (await s.execute(
            select(AuditLog).where(AuditLog.entity_id == job_id).order_by(AuditLog.created_at)
        )).scalars().all()
        events = [l.event_type for l in logs]

    assert "INGESTION_REQUESTED" in events
    assert "INGESTION_STARTED" in events
    assert "INGESTION_COMPLETED" in events


@pytest.mark.asyncio
async def test_pagination(client: AsyncClient, unique_email):
    token, org_id = await _setup_owner_org(client, unique_email)
    resource_id = await _upload(client, token, org_id)
    headers = {"Authorization": f"Bearer {token}"}

    r1 = await _ingest(client, token, org_id, resource_id)
    await _poll(client, token, org_id, resource_id, r1.json()["id"], timeout=30)
    r2 = await _ingest(client, token, org_id, resource_id, force=True)
    await _poll(client, token, org_id, resource_id, r2.json()["id"], timeout=30)

    all_r = await client.get(f"/api/v1/organizations/{org_id}/resources/{resource_id}/ingestions", headers=headers)
    assert all_r.json()["total"] >= 2

    p1 = await client.get(f"/api/v1/organizations/{org_id}/resources/{resource_id}/ingestions?limit=1&offset=0", headers=headers)
    assert len(p1.json()["items"]) == 1
    p2 = await client.get(f"/api/v1/organizations/{org_id}/resources/{resource_id}/ingestions?limit=1&offset=1", headers=headers)
    assert p2.json()["items"][0]["id"] != p1.json()["items"][0]["id"]


@pytest.mark.asyncio
async def test_worker_failure_corrupted(client: AsyncClient, unique_email):
    token, org_id = await _setup_owner_org(client, unique_email)
    resource_id = await _upload(client, token, org_id, b"\xff\xfe\x00\x00\x80\x81\x82", "bad.txt")
    r = await _ingest(client, token, org_id, resource_id)
    assert r.status_code == 202
    job_id = r.json()["id"]

    final = await _poll(client, token, org_id, resource_id, job_id, timeout=30)
    assert final["status"] == "FAILED"
    assert final["error_code"] == "CORRUPTED_DOCUMENT"


@pytest.mark.asyncio
async def test_failure_atomicity(client: AsyncClient, unique_email):
    token, org_id = await _setup_owner_org(client, unique_email)
    headers = {"Authorization": f"Bearer {token}"}

    good_id = await _upload(client, token, org_id, b"Good content here")
    r1 = await _ingest(client, token, org_id, good_id)
    final1 = await _poll(client, token, org_id, good_id, r1.json()["id"], timeout=30)
    assert final1["status"] == "COMPLETED"

    doc1 = await client.get(f"/api/v1/organizations/{org_id}/resources/{good_id}/document", headers=headers)
    assert doc1.status_code == 200
    original_text = doc1.json()["plain_text"]

    bad_id = await _upload(client, token, org_id, b"\xff\xfe\x00\x00bad", "broken.txt")
    r2 = await _ingest(client, token, org_id, bad_id)
    final2 = await _poll(client, token, org_id, bad_id, r2.json()["id"], timeout=30)
    assert final2["status"] == "FAILED"

    doc_good_still = await client.get(f"/api/v1/organizations/{org_id}/resources/{good_id}/document", headers=headers)
    assert doc_good_still.status_code == 200
    assert doc_good_still.json()["plain_text"] == original_text

    doc_bad = await client.get(f"/api/v1/organizations/{org_id}/resources/{bad_id}/document", headers=headers)
    assert doc_bad.status_code == 404, "Failed ingestion must not expose partial document"


@pytest.mark.asyncio
async def test_retry_permanent_errors_not_retried(client: AsyncClient, unique_email):
    from workers.system_tasks import PERMANENT_ERROR_CODES
    assert "CORRUPTED_DOCUMENT" in PERMANENT_ERROR_CODES
    assert "ENCRYPTED_PDF" in PERMANENT_ERROR_CODES
    assert "OCR_REQUIRED" in PERMANENT_ERROR_CODES
    assert "PAGE_LIMIT_EXCEEDED" in PERMANENT_ERROR_CODES
    assert "TEXT_LIMIT_EXCEEDED" in PERMANENT_ERROR_CODES
    assert "ZIP_LIMIT_EXCEEDED" in PERMANENT_ERROR_CODES

    token, org_id = await _setup_owner_org(client, unique_email)
    resource_id = await _upload(client, token, org_id, b"\xff\xfe\x00\x00bad", "perm_fail.txt")
    r = await _ingest(client, token, org_id, resource_id)
    assert r.status_code == 202

    final = await _poll(client, token, org_id, resource_id, r.json()["id"], timeout=20)
    assert final["status"] == "FAILED"
    assert final["error_code"] == "CORRUPTED_DOCUMENT"






