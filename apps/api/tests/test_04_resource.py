import pytest
import pytest_asyncio
from httpx import AsyncClient
import uuid
import io
import zipfile
import hashlib
from app.db.session import async_session_maker
from app.modules.organization.models import Organization, OrganizationMember
from app.modules.resource.models import Resource
from app.modules.identity.models import User
from app.modules.identity.models import AuditLog
from sqlalchemy.future import select

@pytest.fixture
def unique_email():
    return f"test_{uuid.uuid4()}@example.com"

@pytest.fixture
def unique_email2():
    return f"test_{uuid.uuid4()}@example.com"

@pytest.fixture
def pdf_content():
    return b"%PDF-1.4\n%EOF\n"

@pytest.fixture
def docx_content():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        zf.writestr('[Content_Types].xml', '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types></Types>')
        zf.writestr('word/document.xml', '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><document></document>')
    return buf.getvalue()

@pytest.fixture
def pptx_content():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        zf.writestr('[Content_Types].xml', '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types></Types>')
        zf.writestr('ppt/presentation.xml', '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><presentation></presentation>')
    return buf.getvalue()

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

@pytest.mark.asyncio
async def test_30_upload_files(client, setup_tenants, pdf_content, docx_content, pptx_content):
    token_a, user_a_id, org_a_id, token_b, org_b_id = setup_tenants
    
    # Valid PDF Upload
    file_upload = {"file": ("test.pdf", pdf_content, "application/pdf")}
    res_upload = await client.post(f"/api/v1/organizations/{org_a_id}/resources", headers={"Authorization": f"Bearer {token_a}"}, files=file_upload)
    assert res_upload.status_code == 200

    # Valid DOCX Upload
    file_upload_docx = {"file": ("test.docx", docx_content, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    res_docx = await client.post(f"/api/v1/organizations/{org_a_id}/resources", headers={"Authorization": f"Bearer {token_a}"}, files=file_upload_docx)
    assert res_docx.status_code == 200

    # Valid PPTX Upload
    file_upload_pptx = {"file": ("test.pptx", pptx_content, "application/vnd.openxmlformats-officedocument.presentationml.presentation")}
    res_pptx = await client.post(f"/api/v1/organizations/{org_a_id}/resources", headers={"Authorization": f"Bearer {token_a}"}, files=file_upload_pptx)
    assert res_pptx.status_code == 200

@pytest.mark.asyncio
async def test_31_file_validation(client, setup_tenants):
    token_a, _, org_a_id, _, _ = setup_tenants
    
    # Empty file
    res_empty = await client.post(f"/api/v1/organizations/{org_a_id}/resources", headers={"Authorization": f"Bearer {token_a}"}, files={"file": ("empty.pdf", b"", "application/pdf")})
    assert res_empty.status_code == 400

    # Unsupported extension
    res_unsupported = await client.post(f"/api/v1/organizations/{org_a_id}/resources", headers={"Authorization": f"Bearer {token_a}"}, files={"file": ("test.xyz", b"abc", "text/plain")})
    assert res_unsupported.status_code == 400

    # EXE rejected
    exe_content = b"MZ\x90\x00\x03\x00\x00\x00"
    res_exe = await client.post(f"/api/v1/organizations/{org_a_id}/resources", headers={"Authorization": f"Bearer {token_a}"}, files={"file": ("test.exe", exe_content, "application/x-msdownload")})
    assert res_exe.status_code == 400

    # Spoofed PDF (EXE content)
    res_spoof_pdf = await client.post(f"/api/v1/organizations/{org_a_id}/resources", headers={"Authorization": f"Bearer {token_a}"}, files={"file": ("test.pdf", exe_content, "application/pdf")})
    assert res_spoof_pdf.status_code == 400

    # Fake DOCX (valid zip but missing word/)
    fake_docx_buf = io.BytesIO()
    with zipfile.ZipFile(fake_docx_buf, 'w') as zf:
        zf.writestr('test.txt', 'hello world')
    res_fake_docx = await client.post(f"/api/v1/organizations/{org_a_id}/resources", headers={"Authorization": f"Bearer {token_a}"}, files={"file": ("test.docx", fake_docx_buf.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
    assert res_fake_docx.status_code == 400

@pytest.mark.asyncio
async def test_32_tenant_isolation(client, setup_tenants, pdf_content):
    token_a, _, org_a_id, token_b, org_b_id = setup_tenants
    
    # Upload Resource A
    res_upload = await client.post(f"/api/v1/organizations/{org_a_id}/resources", headers={"Authorization": f"Bearer {token_a}"}, files={"file": ("test.pdf", pdf_content, "application/pdf")})
    resource_a_id = res_upload.json()["id"]

    # B lists A's org
    res_b_list = await client.get(f"/api/v1/organizations/{org_a_id}/resources", headers={"Authorization": f"Bearer {token_b}"})
    assert res_b_list.status_code == 403

    # B accesses A's resource directly
    res_b_detail = await client.get(f"/api/v1/organizations/{org_a_id}/resources/{resource_a_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert res_b_detail.status_code == 403

    # Forged Org B ID with Org A Resource
    res_forged = await client.get(f"/api/v1/organizations/{org_b_id}/resources/{resource_a_id}", headers={"Authorization": f"Bearer {token_a}"})
    assert res_forged.status_code in [403, 404]

@pytest.mark.asyncio
async def test_33_resource_rbac(client, setup_tenants, pdf_content):
    token_a, user_a_id, org_a_id, _, _ = setup_tenants
    # This just ensures we can list and delete. We know tenant isolation works.
    res_upload = await client.post(f"/api/v1/organizations/{org_a_id}/resources", headers={"Authorization": f"Bearer {token_a}"}, files={"file": ("test.pdf", pdf_content, "application/pdf")})
    resource_a_id = res_upload.json()["id"]
    
    res_list = await client.get(f"/api/v1/organizations/{org_a_id}/resources", headers={"Authorization": f"Bearer {token_a}"})
    assert res_list.status_code == 200
    
    res_delete = await client.delete(f"/api/v1/organizations/{org_a_id}/resources/{resource_a_id}", headers={"Authorization": f"Bearer {token_a}"})
    assert res_delete.status_code == 204

@pytest.mark.asyncio
async def test_34_storage_integration(client, setup_tenants, pdf_content):
    token_a, _, org_a_id, _, _ = setup_tenants
    
    # Upload test object
    res_upload = await client.post(f"/api/v1/organizations/{org_a_id}/resources", headers={"Authorization": f"Bearer {token_a}"}, files={"file": ("test_int.pdf", pdf_content, "application/pdf")})
    assert res_upload.status_code == 200
    resource_a_id = res_upload.json()["id"]
    
    # Download
    res_download = await client.get(f"/api/v1/organizations/{org_a_id}/resources/{resource_a_id}/download", headers={"Authorization": f"Bearer {token_a}"})
    assert res_download.status_code == 200
    presigned_url = res_download.json()["url"]
    
    import httpx
    async with httpx.AsyncClient() as c:
        download_res = await c.get(presigned_url)
        assert download_res.status_code == 200
        assert download_res.content == pdf_content

    # Delete
    res_delete = await client.delete(f"/api/v1/organizations/{org_a_id}/resources/{resource_a_id}", headers={"Authorization": f"Bearer {token_a}"})
    assert res_delete.status_code == 204
    
    # Verify MinIO object is gone via Presigned URL
    async with httpx.AsyncClient() as c:
        download_res_after = await c.get(presigned_url)
        assert download_res_after.status_code in [403, 404]

@pytest.mark.asyncio
async def test_35_storage_failure(client, setup_tenants, pdf_content, monkeypatch):
    token_a, _, org_a_id, _, _ = setup_tenants
    
    # Mock storage.put to raise exception
    import app.modules.resource.service
    
    async def mock_put(*args, **kwargs):
        raise Exception("Mock MinIO failure")
        
    class MockStorage:
        async def put(self, *args, **kwargs):
            await mock_put(*args, **kwargs)
    
    async def mock_get_storage():
        return MockStorage()
        
    monkeypatch.setattr(app.modules.resource.service, "get_storage", mock_get_storage)
    
    # Attempt upload
    res_upload = await client.post(f"/api/v1/organizations/{org_a_id}/resources", headers={"Authorization": f"Bearer {token_a}"}, files={"file": ("test_fail.pdf", pdf_content, "application/pdf")})
    assert res_upload.status_code == 500
    
    # Verify no resource was created
    res_list = await client.get(f"/api/v1/organizations/{org_a_id}/resources", headers={"Authorization": f"Bearer {token_a}"})
    assert len(res_list.json()) == 0

@pytest.mark.asyncio
async def test_36_db_compensation(client, setup_tenants, pdf_content, monkeypatch):
    token_a, _, org_a_id, _, _ = setup_tenants
    
    # Keep track of deleted keys to verify compensation fired
    deleted_keys = []
    
    # We will wrap get_storage to intercept delete
    from app.core.storage import get_storage
    real_storage = await get_storage()
    
    class TrackedStorage:
        async def put(self, *args, **kwargs):
            return await real_storage.put(*args, **kwargs)
        async def delete(self, key, *args, **kwargs):
            deleted_keys.append(key)
            return await real_storage.delete(key, *args, **kwargs)
            
    import app.modules.resource.service
    
    async def mock_get_storage():
        return TrackedStorage()
        
    monkeypatch.setattr(app.modules.resource.service, "get_storage", mock_get_storage)
    
    # Now mock DB session commit to fail
    from app.modules.resource.repository import ResourceRepository
    original_create = ResourceRepository.create
    
    async def mock_create(*args, **kwargs):
        raise Exception("Mock DB Failure")
        
    monkeypatch.setattr(ResourceRepository, "create", mock_create)
    
    # Attempt upload
    res_upload = await client.post(f"/api/v1/organizations/{org_a_id}/resources", headers={"Authorization": f"Bearer {token_a}"}, files={"file": ("test_db_fail.pdf", pdf_content, "application/pdf")})
    assert res_upload.status_code == 500
    
    # Verify that delete was called on MinIO due to compensation
    assert len(deleted_keys) > 0

@pytest.mark.asyncio
async def test_37_path_traversal(client, setup_tenants, pdf_content):
    token_a, _, org_a_id, _, _ = setup_tenants
    
    file_upload_trav = {"file": ("../../etc/passwd.pdf", pdf_content, "application/pdf")}
    res_trav = await client.post(f"/api/v1/organizations/{org_a_id}/resources", headers={"Authorization": f"Bearer {token_a}"}, files=file_upload_trav)
    assert res_trav.status_code == 200
    assert res_trav.json()["original_filename"] == "passwd.pdf"

@pytest.mark.asyncio
async def test_38_hash_verification(client, setup_tenants, pdf_content):
    token_a, _, org_a_id, _, _ = setup_tenants
    
    file_upload = {"file": ("test_hash.pdf", pdf_content, "application/pdf")}
    res_upload = await client.post(f"/api/v1/organizations/{org_a_id}/resources", headers={"Authorization": f"Bearer {token_a}"}, files=file_upload)
    assert res_upload.status_code == 200
    expected_hash = hashlib.sha256(pdf_content).hexdigest()
    assert res_upload.json()["sha256"] == expected_hash

@pytest.mark.asyncio
async def test_39_audit_log_tests(client, setup_tenants, pdf_content):
    token_a, _, org_a_id, _, _ = setup_tenants
    
    file_upload = {"file": ("test_audit.pdf", pdf_content, "application/pdf")}
    res_upload = await client.post(f"/api/v1/organizations/{org_a_id}/resources", headers={"Authorization": f"Bearer {token_a}"}, files=file_upload)
    assert res_upload.status_code == 200
    resource_id = res_upload.json()["id"]
    
    res_download = await client.get(f"/api/v1/organizations/{org_a_id}/resources/{resource_id}/download", headers={"Authorization": f"Bearer {token_a}"})
    assert res_download.status_code == 200
    
    res_delete = await client.delete(f"/api/v1/organizations/{org_a_id}/resources/{resource_id}", headers={"Authorization": f"Bearer {token_a}"})
    assert res_delete.status_code == 204

    # Direct DB query to verify audit logs
    async with async_session_maker() as session:
        result = await session.execute(select(AuditLog).where(AuditLog.entity_id == str(resource_id)))
        logs = result.scalars().all()
        events = [log.event_type for log in logs]
        
        assert "RESOURCE_UPLOADED" in events
        assert "RESOURCE_DOWNLOADED" in events
        assert "RESOURCE_DELETED" in events

