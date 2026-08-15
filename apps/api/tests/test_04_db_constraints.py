import pytest
from sqlalchemy.exc import IntegrityError
import uuid
from app.db.session import async_session_maker
from app.modules.identity.models import User, Role, Permission, RolePermission
from app.modules.organization.models import Organization, OrganizationMember

@pytest.fixture
def unique_email():
    return f"test_{uuid.uuid4()}@example.com"

@pytest.mark.asyncio
async def test_16_duplicate_normalized_email_constraint(unique_email):
    # 29 duplicate normalized email constraint
    async with async_session_maker() as session:
        u1 = User(
            email=f"A_{unique_email}",
            email_normalized=unique_email.lower(),
            password_hash="hash"
        )
        session.add(u1)
        await session.commit()
        
        u2 = User(
            email=f"B_{unique_email}",
            email_normalized=unique_email.lower(),
            password_hash="hash"
        )
        session.add(u2)
        try:
            await session.commit()
            assert False, "Should raise IntegrityError"
        except IntegrityError:
            await session.rollback()

@pytest.mark.asyncio
async def test_17_duplicate_membership_constraint(unique_email):
    # 28 duplicate membership constraint
    async with async_session_maker() as session:
        u = User(email=f"C_{unique_email}", email_normalized=f"c_{unique_email}", password_hash="hash")
        session.add(u)
        
        org = Organization(name="Test Org", slug=f"test-org-{uuid.uuid4()}")
        session.add(org)
        await session.flush()
        
        m1 = OrganizationMember(organization_id=org.id, user_id=u.id)
        session.add(m1)
        await session.commit()
        
        m2 = OrganizationMember(organization_id=org.id, user_id=u.id)
        session.add(m2)
        try:
            await session.commit()
            assert False, "Should raise IntegrityError"
        except IntegrityError:
            await session.rollback()

@pytest.mark.asyncio
async def test_18_duplicate_role_permission(unique_email):
    async with async_session_maker() as session:
        role = Role(name=f"test_role_{uuid.uuid4()}")
        session.add(role)
        perm = Permission(name=f"test_perm_{uuid.uuid4()}")
        session.add(perm)
        await session.flush()
        
        rp1 = RolePermission(role_id=role.id, permission_id=perm.id)
        session.add(rp1)
        await session.commit()
        
        rp2 = RolePermission(role_id=role.id, permission_id=perm.id)
        session.add(rp2)
        try:
            await session.commit()
            assert False, "Should raise IntegrityError"
        except IntegrityError:
            await session.rollback()
