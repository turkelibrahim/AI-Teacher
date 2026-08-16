import uuid
from typing import Optional, List, Tuple
from datetime import datetime, timezone
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .models import ResourceIngestionJob, ResourceDocument, ResourcePage

class IngestionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_job(self, organization_id: uuid.UUID, resource_id: uuid.UUID, requested_by_user_id: uuid.UUID) -> ResourceIngestionJob:
        job = ResourceIngestionJob(
            organization_id=organization_id,
            resource_id=resource_id,
            requested_by_user_id=requested_by_user_id,
            status="PENDING"
        )
        self.session.add(job)
        await self.session.flush()
        return job

    async def get_job(self, organization_id: uuid.UUID, resource_id: uuid.UUID, job_id: uuid.UUID) -> Optional[ResourceIngestionJob]:
        result = await self.session.execute(
            select(ResourceIngestionJob)
            .where(
                ResourceIngestionJob.id == job_id,
                ResourceIngestionJob.organization_id == organization_id,
                ResourceIngestionJob.resource_id == resource_id
            )
        )
        return result.scalars().first()
        
    async def get_job_by_id_only(self, job_id: uuid.UUID) -> Optional[ResourceIngestionJob]:
        result = await self.session.execute(
            select(ResourceIngestionJob).where(ResourceIngestionJob.id == job_id)
        )
        return result.scalars().first()

    async def get_latest_job(self, organization_id: uuid.UUID, resource_id: uuid.UUID) -> Optional[ResourceIngestionJob]:
        result = await self.session.execute(
            select(ResourceIngestionJob)
            .where(
                ResourceIngestionJob.organization_id == organization_id,
                ResourceIngestionJob.resource_id == resource_id
            )
            .order_by(ResourceIngestionJob.created_at.desc())
            .limit(1)
        )
        return result.scalars().first()

    async def list_jobs(self, organization_id: uuid.UUID, resource_id: uuid.UUID, limit: int = 100, offset: int = 0) -> Tuple[List[ResourceIngestionJob], int]:
        from sqlalchemy import func
        count_result = await self.session.execute(
            select(func.count(ResourceIngestionJob.id))
            .where(
                ResourceIngestionJob.organization_id == organization_id,
                ResourceIngestionJob.resource_id == resource_id
            )
        )
        total = count_result.scalar() or 0
        
        result = await self.session.execute(
            select(ResourceIngestionJob)
            .where(
                ResourceIngestionJob.organization_id == organization_id,
                ResourceIngestionJob.resource_id == resource_id
            )
            .order_by(ResourceIngestionJob.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all()), total

    async def update_job_status(self, job_id: uuid.UUID, status: str, **kwargs) -> Optional[ResourceIngestionJob]:
        stmt = (
            update(ResourceIngestionJob)
            .where(ResourceIngestionJob.id == job_id)
            .values(status=status, updated_at=datetime.now(timezone.utc), **kwargs)
            .returning(ResourceIngestionJob)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def claim_job(self, job_id: uuid.UUID) -> Optional[ResourceIngestionJob]:
        # Atomic transition QUEUED -> PROCESSING
        stmt = (
            update(ResourceIngestionJob)
            .where(ResourceIngestionJob.id == job_id, ResourceIngestionJob.status == "QUEUED")
            .values(status="PROCESSING", started_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc))
            .returning(ResourceIngestionJob)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def create_document(self, doc: ResourceDocument) -> ResourceDocument:
        self.session.add(doc)
        await self.session.flush()
        return doc
        
    async def get_document(self, organization_id: uuid.UUID, resource_id: uuid.UUID) -> Optional[ResourceDocument]:
        result = await self.session.execute(
            select(ResourceDocument)
            .join(ResourceIngestionJob, ResourceDocument.ingestion_job_id == ResourceIngestionJob.id)
            .where(
                ResourceDocument.organization_id == organization_id,
                ResourceDocument.resource_id == resource_id,
                ResourceIngestionJob.status == "COMPLETED"
            )
            .order_by(ResourceIngestionJob.completed_at.desc())
            .limit(1)
        )
        return result.scalars().first()

    async def create_pages(self, pages: List[ResourcePage]):
        self.session.add_all(pages)
        await self.session.flush()

    async def get_pages(self, organization_id: uuid.UUID, resource_id: uuid.UUID, limit: int = 100, offset: int = 0) -> Tuple[List[ResourcePage], int]:
        doc = await self.get_document(organization_id, resource_id)
        if not doc:
            return [], 0

        from sqlalchemy import func
        count_result = await self.session.execute(
            select(func.count(ResourcePage.id))
            .where(
                ResourcePage.ingestion_job_id == doc.ingestion_job_id
            )
        )
        total = count_result.scalar() or 0
        
        result = await self.session.execute(
            select(ResourcePage)
            .where(
                ResourcePage.ingestion_job_id == doc.ingestion_job_id
            )
            .order_by(ResourcePage.page_number)
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all()), total
        
    async def get_page(self, organization_id: uuid.UUID, resource_id: uuid.UUID, page_number: int) -> Optional[ResourcePage]:
        doc = await self.get_document(organization_id, resource_id)
        if not doc:
            return None
        result = await self.session.execute(
            select(ResourcePage)
            .where(
                ResourcePage.ingestion_job_id == doc.ingestion_job_id,
                ResourcePage.page_number == page_number
            )
        )
        return result.scalars().first()
        
    async def cleanup_failed_job_data(self, job_id: uuid.UUID):
        # Delete any partially extracted pages/document for this job
        await self.session.execute(delete(ResourcePage).where(ResourcePage.ingestion_job_id == job_id))
        await self.session.execute(delete(ResourceDocument).where(ResourceDocument.ingestion_job_id == job_id))





