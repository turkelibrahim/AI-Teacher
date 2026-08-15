from fastapi import APIRouter, Depends
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db_session
from app.modules.organization.schemas import OrganizationResponse, OrganizationMemberResponse
from app.modules.organization.repository import OrganizationRepository
from app.api.deps import get_current_active_user, RequireOrganizationPermission
from app.modules.identity.models import User
import uuid
from pydantic import BaseModel

router = APIRouter()

def get_org_repo(session: AsyncSession = Depends(get_db_session)) -> OrganizationRepository:
    return OrganizationRepository(session)

@router.get("", response_model=List[OrganizationResponse])
async def list_organizations(
    user: User = Depends(get_current_active_user),
    org_repo: OrganizationRepository = Depends(get_org_repo)
):
    memberships = await org_repo.get_user_memberships(user.id)
    return [m.organization for m in memberships]

@router.get("/{organization_id}", response_model=OrganizationResponse)
async def get_organization(
    organization_id: uuid.UUID,
    membership = Depends(RequireOrganizationPermission("organization.read")),
):
    return membership.organization

@router.get("/{organization_id}/members", response_model=List[OrganizationMemberResponse])
async def get_organization_members(
    organization_id: uuid.UUID,
    membership = Depends(RequireOrganizationPermission("organization.members.read")),
    org_repo: OrganizationRepository = Depends(get_org_repo)
):
    members = await org_repo.get_organization_members(organization_id)
    
    response = []
    for m in members:
        roles_str = [r.role.name for r in m.roles]
        response.append(OrganizationMemberResponse(
            id=m.id,
            user_id=m.user_id,
            organization_id=m.organization_id,
            status=m.status,
            roles=roles_str,
            user=m.user
        ))
    return response


class OrganizationUpdate(BaseModel):
    name: str

@router.patch("/{organization_id}", response_model=OrganizationResponse)
async def update_organization(
    organization_id: uuid.UUID,
    data: OrganizationUpdate,
    membership = Depends(RequireOrganizationPermission("organization.update")),
    org_repo: OrganizationRepository = Depends(get_org_repo)
):
    organization = membership.organization
    organization.name = data.name
    await org_repo.session.commit()
    await org_repo.session.refresh(organization)
    return organization
