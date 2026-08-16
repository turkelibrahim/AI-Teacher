from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from app.api.deps import RequireOrganizationPermission
from app.db.session import get_db_session
from app.modules.organization.models import OrganizationMember
from app.modules.ingestion.schemas import (
    IngestionJobResponse,
    StartIngestionRequest,
    ResourceDocumentResponse,
    ResourcePageResponse,
    PaginatedPagesResponse,
    PaginatedIngestionJobResponse
)
from app.modules.ingestion.service import IngestionService

router = APIRouter(prefix="/{organization_id}/resources/{resource_id}/ingestions", tags=["Ingestion"])

@router.post("", response_model=IngestionJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_ingestion(
    organization_id: uuid.UUID,
    resource_id: uuid.UUID,
    request: StartIngestionRequest,
    membership: OrganizationMember = Depends(RequireOrganizationPermission("resource.upload")),
    db: AsyncSession = Depends(get_db_session)
):
    service = IngestionService(db)
    job = await service.start_ingestion(organization_id, resource_id, membership.user_id, request.force)
    return job

@router.get("", response_model=PaginatedIngestionJobResponse)
async def list_ingestion_jobs(
    organization_id: uuid.UUID,
    resource_id: uuid.UUID,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    membership: OrganizationMember = Depends(RequireOrganizationPermission("resource.read")),
    db: AsyncSession = Depends(get_db_session)
):
    service = IngestionService(db)
    items, total = await service.list_jobs(organization_id, resource_id, limit, offset)
    return PaginatedIngestionJobResponse(items=items, total=total, limit=limit, offset=offset)

@router.get("/{job_id}", response_model=IngestionJobResponse)
async def get_ingestion_job(
    organization_id: uuid.UUID,
    resource_id: uuid.UUID,
    job_id: uuid.UUID,
    membership: OrganizationMember = Depends(RequireOrganizationPermission("resource.read")),
    db: AsyncSession = Depends(get_db_session)
):
    service = IngestionService(db)
    return await service.get_job(organization_id, resource_id, job_id)

document_router = APIRouter(prefix="/{organization_id}/resources/{resource_id}", tags=["Ingestion Data"])

@document_router.get("/document", response_model=ResourceDocumentResponse)
async def get_resource_document(
    organization_id: uuid.UUID,
    resource_id: uuid.UUID,
    membership: OrganizationMember = Depends(RequireOrganizationPermission("resource.read")),
    db: AsyncSession = Depends(get_db_session)
):
    service = IngestionService(db)
    return await service.get_document(organization_id, resource_id)

@document_router.get("/pages", response_model=PaginatedPagesResponse)
async def list_resource_pages(
    organization_id: uuid.UUID,
    resource_id: uuid.UUID,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    membership: OrganizationMember = Depends(RequireOrganizationPermission("resource.read")),
    db: AsyncSession = Depends(get_db_session)
):
    service = IngestionService(db)
    items, total = await service.get_pages(organization_id, resource_id, limit, offset)
    return PaginatedPagesResponse(items=items, total=total, limit=limit, offset=offset)

@document_router.get("/pages/{page_number}", response_model=ResourcePageResponse)
async def get_resource_page(
    organization_id: uuid.UUID,
    resource_id: uuid.UUID,
    page_number: int,
    membership: OrganizationMember = Depends(RequireOrganizationPermission("resource.read")),
    db: AsyncSession = Depends(get_db_session)
):
    service = IngestionService(db)
    return await service.get_page(organization_id, resource_id, page_number)
