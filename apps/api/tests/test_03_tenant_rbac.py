import pytest
from httpx import AsyncClient
import uuid
from sqlalchemy.future import select
from app.db.session import async_session_maker
from app.modules.organization.models import Organization, OrganizationMember, MemberRole
from app.modules.identity.models import Role, User

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
    
    # OWNER permissions check
    res_own_read = await client.get(f"/api/v1/organizations/{org_a_id}", headers={"Authorization": f"Bearer {token_a}"})
    assert res_own_read.status_code == 200
    
    res_own_members = await client.get(f"/api/v1/organizations/{org_a_id}/members", headers={"Authorization": f"Bearer {token_a}"})
    assert res_own_members.status_code == 200
    
    res_own_update = await client.patch(f"/api/v1/organizations/{org_a_id}", json={"name": "New Name"}, headers={"Authorization": f"Bearer {token_a}"})
    assert res_own_update.status_code == 200
    
    # Foreign organization denied
    res_foreign_read = await client.get(f"/api/v1/organizations/{org_b_id}", headers={"Authorization": f"Bearer {token_a}"})
    assert res_foreign_read.status_code == 403
    
    res_foreign_members = await client.get(f"/api/v1/organizations/{org_b_id}/members", headers={"Authorization": f"Bearer {token_a}"})
    assert res_foreign_members.status_code == 403
    
    # Now make User B a MEMBER of Org A
    async with async_session_maker() as session:
        new_member = OrganizationMember(organization_id=uuid.UUID(org_a_id), user_id=uuid.UUID(res_b.json()["user"]["id"]), status="ACTIVE")
        session.add(new_member)
        await session.flush()
        
        result = await session.execute(select(Role).where(Role.name == "MEMBER"))
        member_role = result.scalars().first()
        mr = MemberRole(member_id=new_member.id, role_id=member_role.id)
        session.add(mr)
        await session.commit()
        member_role_id = new_member.id
        
    # User B (MEMBER in Org A) test
    res_b_read = await client.get(f"/api/v1/organizations/{org_a_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert res_b_read.status_code == 200
    
    res_b_members = await client.get(f"/api/v1/organizations/{org_a_id}/members", headers={"Authorization": f"Bearer {token_b}"})
    assert res_b_members.status_code == 403
    
    res_b_update = await client.patch(f"/api/v1/organizations/{org_a_id}", json={"name": "New Name 2"}, headers={"Authorization": f"Bearer {token_b}"})
    assert res_b_update.status_code == 403

    # Change User B to INSTRUCTOR
    async with async_session_maker() as session:
        # remove old role
        result = await session.execute(select(MemberRole).where(MemberRole.member_id == member_role_id))
        mr = result.scalars().first()
        await session.delete(mr)
        
        result = await session.execute(select(Role).where(Role.name == "INSTRUCTOR"))
        instr_role = result.scalars().first()
        mr_new = MemberRole(member_id=member_role_id, role_id=instr_role.id)
        session.add(mr_new)
        await session.commit()

    # User B (INSTRUCTOR in Org A) test
    res_b_read = await client.get(f"/api/v1/organizations/{org_a_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert res_b_read.status_code == 200
    
    res_b_members = await client.get(f"/api/v1/organizations/{org_a_id}/members", headers={"Authorization": f"Bearer {token_b}"})
    assert res_b_members.status_code == 200
    
    res_b_update = await client.patch(f"/api/v1/organizations/{org_a_id}", json={"name": "New Name 3"}, headers={"Authorization": f"Bearer {token_b}"})
    assert res_b_update.status_code == 403

    # Change User B to ADMIN
    async with async_session_maker() as session:
        result = await session.execute(select(MemberRole).where(MemberRole.member_id == member_role_id))
        mr = result.scalars().first()
        await session.delete(mr)
        
        result = await session.execute(select(Role).where(Role.name == "ADMIN"))
        admin_role = result.scalars().first()
        mr_new = MemberRole(member_id=member_role_id, role_id=admin_role.id)
        session.add(mr_new)
        await session.commit()

    # User B (ADMIN in Org A) test
    res_b_read = await client.get(f"/api/v1/organizations/{org_a_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert res_b_read.status_code == 200
    
    res_b_members = await client.get(f"/api/v1/organizations/{org_a_id}/members", headers={"Authorization": f"Bearer {token_b}"})
    assert res_b_members.status_code == 200
    
    res_b_update = await client.patch(f"/api/v1/organizations/{org_a_id}", json={"name": "New Name 4"}, headers={"Authorization": f"Bearer {token_b}"})
    assert res_b_update.status_code == 200

@pytest.mark.asyncio
async def test_21_superuser_separation(client):
    unique = f"test_{uuid.uuid4()}@example.com"
    res = await client.post("/api/v1/auth/register", json={"email": unique, "password": "Password123!"})
    user_id = res.json()["user"]["id"]
    
    async with async_session_maker() as session:
        result = await session.execute(select(User).where(User.id == uuid.UUID(user_id)))
        user = result.scalars().first()
        assert user.is_superuser == False

@pytest.mark.asyncio
async def test_22_membership_status_security(client):
    owner_email = f"test_{uuid.uuid4()}@example.com"
    member_email = f"test_{uuid.uuid4()}@example.com"
    
    res_owner = await client.post("/api/v1/auth/register", json={"email": owner_email, "password": "Password123!"})
    token_owner = res_owner.json()["access_token"]
    
    res_member = await client.post("/api/v1/auth/register", json={"email": member_email, "password": "Password123!"})
    token_member = res_member.json()["access_token"]
    member_id = res_member.json()["user"]["id"]
    
    orgs_res = await client.get("/api/v1/organizations", headers={"Authorization": f"Bearer {token_owner}"})
    org_id = orgs_res.json()[0]["id"]
    
    # Add as SUSPENDED
    async with async_session_maker() as session:
        m = OrganizationMember(organization_id=uuid.UUID(org_id), user_id=uuid.UUID(member_id), status="SUSPENDED")
        session.add(m)
        await session.flush()
        result = await session.execute(select(Role).where(Role.name == "ADMIN"))
        session.add(MemberRole(member_id=m.id, role_id=result.scalars().first().id))
        await session.commit()
        m_id = m.id
        
    res = await client.get(f"/api/v1/organizations/{org_id}", headers={"Authorization": f"Bearer {token_member}"})
    assert res.status_code == 403
    
    # Change to INVITED
    async with async_session_maker() as session:
        result = await session.execute(select(OrganizationMember).where(OrganizationMember.id == m_id))
        m = result.scalars().first()
        m.status = "INVITED"
        await session.commit()
        
    res = await client.get(f"/api/v1/organizations/{org_id}", headers={"Authorization": f"Bearer {token_member}"})
    assert res.status_code == 403

    # Change to REMOVED
    async with async_session_maker() as session:
        result = await session.execute(select(OrganizationMember).where(OrganizationMember.id == m_id))
        m = result.scalars().first()
        m.status = "REMOVED"
        await session.commit()
        
    res = await client.get(f"/api/v1/organizations/{org_id}", headers={"Authorization": f"Bearer {token_member}"})
    assert res.status_code == 403

    # Change to ACTIVE
    async with async_session_maker() as session:
        result = await session.execute(select(OrganizationMember).where(OrganizationMember.id == m_id))
        m = result.scalars().first()
        m.status = "ACTIVE"
        await session.commit()
        
    res = await client.get(f"/api/v1/organizations/{org_id}", headers={"Authorization": f"Bearer {token_member}"})
    assert res.status_code == 200
