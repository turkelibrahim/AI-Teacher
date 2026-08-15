from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from app.modules.organization.models import Organization, OrganizationMember, MemberRole
from app.modules.identity.models import Role, RolePermission, Permission
import uuid
from typing import Optional, List

class OrganizationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_organization_by_slug(self, slug: str) -> Optional[Organization]:
        result = await self.session.execute(select(Organization).where(Organization.slug == slug))
        return result.scalars().first()

    async def create_organization(self, organization: Organization) -> Organization:
        self.session.add(organization)
        await self.session.flush()
        return organization

    async def create_membership(self, membership: OrganizationMember) -> OrganizationMember:
        self.session.add(membership)
        await self.session.flush()
        return membership

    async def get_role_by_name(self, name: str) -> Optional[Role]:
        result = await self.session.execute(select(Role).where(Role.name == name))
        return result.scalars().first()

    async def create_role(self, role: Role) -> Role:
        self.session.add(role)
        await self.session.flush()
        return role

    async def assign_role_to_member(self, member_role: MemberRole) -> MemberRole:
        self.session.add(member_role)
        await self.session.flush()
        return member_role

    async def get_user_memberships(self, user_id: uuid.UUID) -> List[OrganizationMember]:
        result = await self.session.execute(
            select(OrganizationMember)
            .options(selectinload(OrganizationMember.organization), selectinload(OrganizationMember.organization), selectinload(OrganizationMember.roles).selectinload(MemberRole.role))
            .where(OrganizationMember.user_id == user_id, OrganizationMember.status == "ACTIVE")
        )
        return list(result.scalars().all())

    async def get_membership(self, user_id: uuid.UUID, organization_id: uuid.UUID) -> Optional[OrganizationMember]:
        result = await self.session.execute(
            select(OrganizationMember)
            .options(selectinload(OrganizationMember.organization), selectinload(OrganizationMember.roles).selectinload(MemberRole.role))
            .where(OrganizationMember.user_id == user_id, OrganizationMember.organization_id == organization_id, OrganizationMember.status == "ACTIVE")
        )
        return result.scalars().first()

    async def get_membership_with_roles(self, user_id: uuid.UUID, organization_id: uuid.UUID) -> Optional[OrganizationMember]:
        result = await self.session.execute(
            select(OrganizationMember)
            .options(
                selectinload(OrganizationMember.organization), selectinload(OrganizationMember.roles)
                .selectinload(MemberRole.role)
                .selectinload(Role.permissions)
                .selectinload(RolePermission.permission)
            )
            .where(OrganizationMember.user_id == user_id, OrganizationMember.organization_id == organization_id, OrganizationMember.status == "ACTIVE")
        )
        return result.scalars().first()

    async def get_organization_by_id(self, org_id: uuid.UUID) -> Optional[Organization]:
        result = await self.session.execute(select(Organization).where(Organization.id == org_id))
        return result.scalars().first()

    async def get_organization_members(self, org_id: uuid.UUID) -> List[OrganizationMember]:
        result = await self.session.execute(
            select(OrganizationMember)
            .options(selectinload(OrganizationMember.user), selectinload(OrganizationMember.organization), selectinload(OrganizationMember.roles).selectinload(MemberRole.role))
            .where(OrganizationMember.organization_id == org_id)
        )
        return list(result.scalars().all())

