from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.db.session import get_db_session
from app.api.deps import RequireOrganizationPermission
from app.modules.identity.schemas import UserResponse
from app.modules.retrieval.schemas import SearchRequest, SearchResponse, IndexingJobResponse
from app.modules.retrieval.service import RetrievalService
from app.modules.retrieval.repository import RetrievalRepository

logger = logging.getLogger("canli_ogretmen.retrieval.router")

router = APIRouter()

@router.post("/{organization_id}/retrieval/search", response_model=SearchResponse)
async def search_chunks(
    organization_id: UUID,
    request: SearchRequest,
    db: AsyncSession = Depends(get_db_session),
    membership = Depends(RequireOrganizationPermission("resource.read"))
):
    service = RetrievalService(db)
    return await service.search(organization_id, request)

@router.get("/{organization_id}/indexings/{job_id}", response_model=IndexingJobResponse)
async def get_indexing_job(
    organization_id: UUID,
    job_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    membership = Depends(RequireOrganizationPermission("resource.read"))
):
    repo = RetrievalRepository(db)
    job = await repo.get_indexing_job(job_id, organization_id)
    if not job:
        raise HTTPException(status_code=404, detail="Indexing job not found")
    
    return IndexingJobResponse(
        id=job.id,
        resource_id=job.resource_id,
        status=job.status,
        total_chunks=job.total_chunks,
        created_at=job.created_at,
        error_message=job.error_message
    )


