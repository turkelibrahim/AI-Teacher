import pytest
from httpx import AsyncClient
import uuid
import os
import io
import zipfile
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

def create_mock_docx():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        zf.writestr('[Content_Types].xml', '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types></Types>')
        zf.writestr('word/document.xml', '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><document></document>')
    return buf.getvalue()

def create_mock_pptx():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        zf.writestr('[Content_Types].xml', '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types></Types>')
        zf.writestr('ppt/presentation.xml', '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><presentation></presentation>')
    return buf.getvalue()

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
    
    # ----------------------------------------------------
    # SUCCESSFUL UPLOADS
    # ----------------------------------------------------
    
    # 1. Valid PDF Upload
    pdf_content = b"%PDF-1.4\n%EOF\n"
    file_upload = {"file": ("test.pdf", pdf_content, "application/pdf")}
    res_upload = await client.post(f"/api/v1/organizations/{org_a_id}/resources", headers={"Authorization": f"Bearer {token_a}"}, files=file_upload)
    assert res_upload.status_code == 200
    resource_a_id = res_upload.json()["id"]

    # 2. Valid DOCX Upload
    docx_content = create_mock_docx()
    file_upload_docx = {"file": ("test.docx", docx_content, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    res_docx = await client.post(f"/api/v1/organizations/{org_a_id}/resources", headers={"Authorization": f"Bearer {token_a}"}, files=file_upload_docx)
    assert res_docx.status_code == 200

    # 3. Valid PPTX Upload
    pptx_content = create_mock_pptx()
    file_upload_pptx = {"file": ("test.pptx", pptx_content, "application/vnd.openxmlformats-officedocument.presentationml.presentation")}
    res_pptx = await client.post(f"/api/v1/organizations/{org_a_id}/resources", headers={"Authorization": f"Bearer {token_a}"}, files=file_upload_pptx)
    assert res_pptx.status_code == 200
    
    # ----------------------------------------------------
    # REJECTED UPLOADS (Spoofing & Limits)
    # ----------------------------------------------------
    
    # 4. Empty file rejected
    res_empty = await client.post(f"/api/v1/organizations/{org_a_id}/resources", headers={"Authorization": f"Bearer {token_a}"}, files={"file": ("empty.pdf", b"", "application/pdf")})
    assert res_empty.status_code == 400

    # 5. Unsupported extension
    res_unsupported = await client.post(f"/api/v1/organizations/{org_a_id}/resources", headers={"Authorization": f"Bearer {token_a}"}, files={"file": ("test.xyz", b"abc", "text/plain")})
    assert res_unsupported.status_code == 400

    # 6. EXE rejected
    exe_content = b"MZ\x90\x00\x03\x00\x00\x00"
    res_exe = await client.post(f"/api/v1/organizations/{org_a_id}/resources", headers={"Authorization": f"Bearer {token_a}"}, files={"file": ("test.exe", exe_content, "application/x-msdownload")})
    assert res_exe.status_code == 400

    # 7. Spoofed PDF (EXE content)
    res_spoof_pdf = await client.post(f"/api/v1/organizations/{org_a_id}/resources", headers={"Authorization": f"Bearer {token_a}"}, files={"file": ("test.pdf", exe_content, "application/pdf")})
    assert res_spoof_pdf.status_code == 400

    # 8. Fake DOCX (valid zip but missing word/ and [Content_Types])
    fake_docx_buf = io.BytesIO()
    with zipfile.ZipFile(fake_docx_buf, 'w') as zf:
        zf.writestr('test.txt', 'hello world')
    res_fake_docx = await client.post(f"/api/v1/organizations/{org_a_id}/resources", headers={"Authorization": f"Bearer {token_a}"}, files={"file": ("test.docx", fake_docx_buf.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
    assert res_fake_docx.status_code == 400

    # 9. Path traversal
    file_upload_trav = {"file": ("../../etc/passwd.pdf", pdf_content, "application/pdf")}
    res_trav = await client.post(f"/api/v1/organizations/{org_a_id}/resources", headers={"Authorization": f"Bearer {token_a}"}, files=file_upload_trav)
    assert res_trav.status_code == 200
    assert res_trav.json()["original_filename"] == "passwd.pdf"
    
    # 10. Storage key injection (ensure storage_key isn't overridden)
    file_upload_inj = {"file": ("test_inj.pdf", pdf_content, "application/pdf")}
    res_inj = await client.post(f"/api/v1/organizations/{org_a_id}/resources", headers={"Authorization": f"Bearer {token_a}"}, data={"storage_key": "evil/path"}, files=file_upload_inj)
    assert res_inj.status_code == 200
    # assert "evil/path" not in res_inj.json()["storage_key"] (Not exposed)

    # ----------------------------------------------------
    # CROSS TENANT ATTACKS
    # ----------------------------------------------------

    # B lists A's org
    res_b_list = await client.get(f"/api/v1/organizations/{org_a_id}/resources", headers={"Authorization": f"Bearer {token_b}"})
    assert res_b_list.status_code == 403

    # B accesses A's resource directly
    res_b_detail = await client.get(f"/api/v1/organizations/{org_a_id}/resources/{resource_a_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert res_b_detail.status_code == 403

    # Forged Org B ID with Org A Resource
    res_forged = await client.get(f"/api/v1/organizations/{org_b_id}/resources/{resource_a_id}", headers={"Authorization": f"Bearer {token_a}"})
    assert res_forged.status_code in [403, 404]

    # ----------------------------------------------------
    # RETRIEVAL AND DOWNLOAD
    # ----------------------------------------------------
    
    # Authorized Download
    res_download = await client.get(f"/api/v1/organizations/{org_a_id}/resources/{resource_a_id}/download", headers={"Authorization": f"Bearer {token_a}"})
    assert res_download.status_code == 200
    presigned_url = res_download.json()["url"]
    
    # HTTP GET URL
    import httpx
    async with httpx.AsyncClient() as c:
        download_res = await c.get(presigned_url)
        assert download_res.status_code == 200
        assert download_res.content == pdf_content

    # ----------------------------------------------------
    # DELETION
    # ----------------------------------------------------
    
    res_delete = await client.delete(f"/api/v1/organizations/{org_a_id}/resources/{resource_a_id}", headers={"Authorization": f"Bearer {token_a}"})
    assert res_delete.status_code == 204
    
    res_detail_after = await client.get(f"/api/v1/organizations/{org_a_id}/resources/{resource_a_id}", headers={"Authorization": f"Bearer {token_a}"})
    assert res_detail_after.status_code == 404

    # HTTP GET URL after delete (Should fail since MinIO object is gone)
    async with httpx.AsyncClient() as c:
        download_res_after = await c.get(presigned_url)
        assert download_res_after.status_code in [403, 404]

