import pytest
from httpx import AsyncClient
import uuid
import os
from app.db.session import async_session_maker
from app.modules.organization.models import Organization, OrganizationMember
from app.modules.resource.models import Resource
from app.modules.identity.models import User
from sqlalchemy.future import select

@pytest.fixture
def unique_email():
    return f"test_{uuid.uuid4()}@example.com"

@pytest.fixture
def unique_email2():
    return f"test_{uuid.uuid4()}@example.com"

@pytest.mark.asyncio
async def test_30_resource_upload_and_security(client, unique_email, unique_email2):
    # Setup two users/tenants
    res_a = await client.post("/api/v1/auth/register", json={"email": unique_email, "password": "Password123!"})
    token_a = res_a.json()["access_token"]
    user_a_id = res_a.json()["user"]["id"]
    
    res_b = await client.post("/api/v1/auth/register", json={"email": unique_email2, "password": "Password123!"})
    token_b = res_b.json()["access_token"]
    
    orgs_a = await client.get("/api/v1/organizations", headers={"Authorization": f"Bearer {token_a}"})
    org_a_id = orgs_a.json()[0]["id"]
    
    orgs_b = await client.get("/api/v1/organizations", headers={"Authorization": f"Bearer {token_b}"})
    org_b_id = orgs_b.json()[0]["id"]
    
    # Gate 7: Valid PDF Upload (Simulated)
    # Using a fake PDF content
    pdf_content = b"%PDF-1.4\n%EOF\n"
    file_upload = {"file": ("test.pdf", pdf_content, "application/pdf")}
    
    res_upload = await client.post(
        f"/api/v1/organizations/{org_a_id}/resources",
        headers={"Authorization": f"Bearer {token_a}"},
        files=file_upload
    )
    assert res_upload.status_code == 200, f"Upload Failed: {res_upload.status_code} - {res_upload.text}"
    resource_a_id = res_upload.json()["id"]
    
    # Gate 15: DB Metadata correct
    assert res_upload.json()["original_filename"] == "test.pdf"
    assert res_upload.json()["extension"] == ".pdf"
    assert res_upload.json()["status"] == "UPLOADED"
    
    # Gate 14: SHA-256 correct
    import hashlib
    expected_hash = hashlib.sha256(pdf_content).hexdigest()
    assert res_upload.json()["sha256"] == expected_hash

    # Gate 17: Authorized list
    res_list = await client.get(
        f"/api/v1/organizations/{org_a_id}/resources",
        headers={"Authorization": f"Bearer {token_a}"}
    )
    assert res_list.status_code == 200
    assert len(res_list.json()) == 1
    assert res_list.json()[0]["id"] == resource_a_id

    # Gate 18: Authorized Detail
    res_detail = await client.get(
        f"/api/v1/organizations/{org_a_id}/resources/{resource_a_id}",
        headers={"Authorization": f"Bearer {token_a}"}
    )
    assert res_detail.status_code == 200

    # Gate 19: Authorized Download
    res_download = await client.get(
        f"/api/v1/organizations/{org_a_id}/resources/{resource_a_id}/download",
        headers={"Authorization": f"Bearer {token_a}"}
    )
    assert res_download.status_code == 200
    assert "url" in res_download.json()

    # Gate 20-23: Foreign Tenant Denied
    res_b_list = await client.get(
        f"/api/v1/organizations/{org_a_id}/resources",
        headers={"Authorization": f"Bearer {token_b}"}
    )
    assert res_b_list.status_code == 403

    res_b_detail = await client.get(
        f"/api/v1/organizations/{org_a_id}/resources/{resource_a_id}",
        headers={"Authorization": f"Bearer {token_b}"}
    )
    assert res_b_detail.status_code == 403

    res_b_download = await client.get(
        f"/api/v1/organizations/{org_a_id}/resources/{resource_a_id}/download",
        headers={"Authorization": f"Bearer {token_b}"}
    )
    assert res_b_download.status_code == 403
    
    res_b_delete = await client.delete(
        f"/api/v1/organizations/{org_a_id}/resources/{resource_a_id}",
        headers={"Authorization": f"Bearer {token_b}"}
    )
    assert res_b_delete.status_code == 403

    # Gate 24: Forged org/resource combo
    res_forged = await client.get(
        f"/api/v1/organizations/{org_b_id}/resources/{resource_a_id}",
        headers={"Authorization": f"Bearer {token_a}"}
    )
    # The resource doesn't belong to org_b, so 404 or 403. Our repo checks org_id, so 404.
    assert res_forged.status_code in [403, 404]
    
    # Gate 11: Invalid executable rejected
    exe_content = b"MZ\x90\x00\x03\x00\x00\x00"
    file_upload_exe = {"file": ("test.exe", exe_content, "application/x-msdownload")}
    res_exe = await client.post(
        f"/api/v1/organizations/{org_a_id}/resources",
        headers={"Authorization": f"Bearer {token_a}"},
        files=file_upload_exe
    )
    assert res_exe.status_code == 400
    
    # Gate 12: Spoofed MIME rejected
    # Pretend it's a PDF but it's an exe (based on extension and magic)
    file_upload_spoof = {"file": ("test.pdf", exe_content, "application/pdf")}
    res_spoof = await client.post(
        f"/api/v1/organizations/{org_a_id}/resources",
        headers={"Authorization": f"Bearer {token_a}"},
        files=file_upload_spoof
    )
    assert res_spoof.status_code == 400

    # Gate 25: Path Traversal
    file_upload_trav = {"file": ("../../etc/passwd.pdf", pdf_content, "application/pdf")}
    res_trav = await client.post(
        f"/api/v1/organizations/{org_a_id}/resources",
        headers={"Authorization": f"Bearer {token_a}"},
        files=file_upload_trav
    )
    assert res_trav.status_code == 200
    # ensure original_filename was sanitized to just passwd.pdf
    assert res_trav.json()["original_filename"] == "passwd.pdf"
    
    # Gate 29: Delete Behavior
    res_delete = await client.delete(
        f"/api/v1/organizations/{org_a_id}/resources/{resource_a_id}",
        headers={"Authorization": f"Bearer {token_a}"}
    )
    assert res_delete.status_code == 204
    
    res_detail_after = await client.get(
        f"/api/v1/organizations/{org_a_id}/resources/{resource_a_id}",
        headers={"Authorization": f"Bearer {token_a}"}
    )
    assert res_detail_after.status_code == 404



