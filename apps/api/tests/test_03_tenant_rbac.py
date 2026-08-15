import pytest
from httpx import AsyncClient
import uuid
from sqlalchemy.future import select
from app.db.session import async_session_maker
from app.modules.organization.models import Organization, OrganizationMember, MemberRole
from app.modules.identity.models import Role

@pytest.fixture
def unique_email():
    return f"test_{uuid.uuid4()}@example.com"

@pytest.fixture
def unique_email2():
    return f"test_{uuid.uuid4()}@example.com"

@pytest.mark.asyncio
async def test_15_tenant_isolation_and_rbac(client, unique_email, unique_email2):
    # Register User A (Owner of Org A)
    res_a = await client.post("/api/v1/auth/register", json={"email": unique_email, "password": "Password123!"})
    token_a = res_a.json()["access_token"]
    user_a_id = res_a.json()["user"]["id"]
    
    # Register User B (Owner of Org B)
    res_b = await client.post("/api/v1/auth/register", json={"email": unique_email2, "password": "Password123!"})
    token_b = res_b.json()["access_token"]
    
    # User A gets their orgs
    orgs_a_res = await client.get("/api/v1/organizations", headers={"Authorization": f"Bearer {token_a}"})
    assert orgs_a_res.status_code == 200
    org_a_id = orgs_a_res.json()[0]["id"]
    
    # User B gets their orgs
    orgs_b_res = await client.get("/api/v1/organizations", headers={"Authorization": f"Bearer {token_b}"})
    assert orgs_b_res.status_code == 200
    org_b_id = orgs_b_res.json()[0]["id"]
    
    # 21 own organization allowed
    # 25 OWNER permissions
    res_own_read = await client.get(f"/api/v1/organizations/{org_a_id}", headers={"Authorization": f"Bearer {token_a}"})
    assert res_own_read.status_code == 200
    
    res_own_members = await client.get(f"/api/v1/organizations/{org_a_id}/members", headers={"Authorization": f"Bearer {token_a}"})
    assert res_own_members.status_code == 200
    
    # 22 foreign organization denied
    # 23 forged organization id denied
    # 24 foreign organization members denied
    res_foreign_read = await client.get(f"/api/v1/organizations/{org_b_id}", headers={"Authorization": f"Bearer {token_a}"})
    assert res_foreign_read.status_code == 403
    
    res_foreign_members = await client.get(f"/api/v1/organizations/{org_b_id}/members", headers={"Authorization": f"Bearer {token_a}"})
    assert res_foreign_members.status_code == 403

    # Now make User B a MEMBER of Org A to test RBAC
    async with async_session_maker() as session:
        # Create membership
        new_member = OrganizationMember(
            organization_id=uuid.UUID(org_a_id),
            user_id=uuid.UUID(res_b.json()["user"]["id"]),
            status="ACTIVE"
        )
        session.add(new_member)
        await session.flush()
        
        # Get MEMBER role
        result = await session.execute(select(Role).where(Role.name == "MEMBER"))
        member_role = result.scalars().first()
        
        mr = MemberRole(member_id=new_member.id, role_id=member_role.id)
        session.add(mr)
        await session.commit()
        
    # User B (MEMBER in Org A) tries to read Org A
    res_b_read_a = await client.get(f"/api/v1/organizations/{org_a_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert res_b_read_a.status_code == 200 # Allowed (organization.read)
    
    # 26 MEMBER owner action denied (organization.members.read requires more perms usually, wait, SYSTEM_ROLES says MEMBER has organization.read only)
    res_b_members_a = await client.get(f"/api/v1/organizations/{org_a_id}/members", headers={"Authorization": f"Bearer {token_b}"})
    assert res_b_members_a.status_code == 403 # Forbidden (requires organization.members.read)

