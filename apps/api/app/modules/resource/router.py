from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db_session
from app.modules.resource.schemas import ResourceResponse, PresignedUrlResponse
from app.modules.resource.repository import ResourceRepository
from app.modules.resource.service import ResourceService
from app.api.deps import get_current_active_user, RequireOrganizationPermission
from app.modules.identity.models import User
import uuid
from typing import List

router = APIRouter()

def get_resource_repo(session: AsyncSession = Depends(get_db_session)) -> ResourceRepository:
    return ResourceRepository(session)

def get_resource_service(
    repo: ResourceRepository = Depends(get_resource_repo),
    session: AsyncSession = Depends(get_db_session)
) -> ResourceService:
    return ResourceService(repo, session)

@router.get("", response_model=List[ResourceResponse])
async def list_resources(
    organization_id: uuid.UUID,
    membership = Depends(RequireOrganizationPermission("resource.read")),
    repo: ResourceRepository = Depends(get_resource_repo)
):
    return await repo.list_by_organization(organization_id)

@router.post("", response_model=ResourceResponse)
async def upload_resource(
    organization_id: uuid.UUID,
    file: UploadFile = File(...),
    membership = Depends(RequireOrganizationPermission("resource.upload")),
    service: ResourceService = Depends(get_resource_service)
):
    return await service.upload_resource(organization_id, membership.user_id, file)

@router.get("/{resource_id}", response_model=ResourceResponse)
async def get_resource(
    organization_id: uuid.UUID,
    resource_id: uuid.UUID,
    membership = Depends(RequireOrganizationPermission("resource.read")),
    repo: ResourceRepository = Depends(get_resource_repo)
):
    resource = await repo.get_by_id(organization_id, resource_id)
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    return resource

@router.get("/{resource_id}/download", response_model=PresignedUrlResponse)
async def download_resource(
    organization_id: uuid.UUID,
    resource_id: uuid.UUID,
    membership = Depends(RequireOrganizationPermission("resource.download")),
    service: ResourceService = Depends(get_resource_service)
):
    url = await service.get_download_url(organization_id, resource_id, membership.user_id)
    from app.core.config import settings
    return PresignedUrlResponse(url=url, expires_in=settings.PRESIGNED_URL_EXPIRE_SECONDS)

@router.delete("/{resource_id}", status_code=204)
async def delete_resource(
    organization_id: uuid.UUID,
    resource_id: uuid.UUID,
    membership = Depends(RequireOrganizationPermission("resource.delete")),
    service: ResourceService = Depends(get_resource_service)
):
    await service.delete_resource(organization_id, resource_id, membership.user_id)

