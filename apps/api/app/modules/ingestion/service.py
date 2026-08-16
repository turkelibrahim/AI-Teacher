import uuid
import logging
from typing import Optional, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
from app.modules.ingestion.repository import IngestionRepository
from app.modules.resource.repository import ResourceRepository
from app.modules.ingestion.models import ResourceIngestionJob, ResourceDocument, ResourcePage
from app.modules.identity.models import AuditLog
# We will import the celery task from workers
from workers.system_tasks import process_resource_ingestion

logger = logging.getLogger(__name__)

class IngestionService:
    def __init__(self, session: AsyncSession):
        self.repository = IngestionRepository(session)
        self.resource_repo = ResourceRepository(session)
        self.session = session

    async def start_ingestion(self, organization_id: uuid.UUID, resource_id: uuid.UUID, user_id: uuid.UUID, force: bool = False) -> ResourceIngestionJob:
        resource = await self.resource_repo.get_by_id(organization_id, resource_id)
        if not resource:
            raise HTTPException(status_code=404, detail="Resource not found")
            
        if not force:
            latest_job = await self.repository.get_latest_job(organization_id, resource_id)
            if latest_job and latest_job.status in ["COMPLETED", "PROCESSING", "QUEUED", "PENDING"]:
                return latest_job
                
        job = await self.repository.create_job(organization_id, resource_id, user_id)
        job = await self.repository.update_job_status(job.id, "QUEUED")
        
        audit_log = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            event_type="INGESTION_REQUESTED",
            entity_type="RESOURCE_INGESTION_JOB",
            entity_id=str(job.id)
        )
        self.session.add(audit_log)
        await self.session.commit()
        
        try:
            process_resource_ingestion.delay(str(job.id))
        except Exception as e:
            logger.error(f"Failed to enqueue ingestion task: {e}")
            job = await self.repository.update_job_status(job.id, "FAILED", error_code="BROKER_UNAVAILABLE", error_message="Failed to enqueue background job")
            await self.session.commit()
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Background worker unavailable. Please try again later.")
        
        return job

    async def get_job(self, organization_id: uuid.UUID, resource_id: uuid.UUID, job_id: uuid.UUID) -> ResourceIngestionJob:
        job = await self.repository.get_job(organization_id, resource_id, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return job

    async def list_jobs(self, organization_id: uuid.UUID, resource_id: uuid.UUID, limit: int = 100, offset: int = 0) -> Tuple[List[ResourceIngestionJob], int]:
        return await self.repository.list_jobs(organization_id, resource_id, limit, offset)

    async def get_document(self, organization_id: uuid.UUID, resource_id: uuid.UUID) -> ResourceDocument:
        doc = await self.repository.get_document(organization_id, resource_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found or ingestion not completed")
        return doc

    async def get_pages(self, organization_id: uuid.UUID, resource_id: uuid.UUID, limit: int = 100, offset: int = 0) -> Tuple[List[ResourcePage], int]:
        return await self.repository.get_pages(organization_id, resource_id, limit, offset)

    async def get_page(self, organization_id: uuid.UUID, resource_id: uuid.UUID, page_number: int) -> ResourcePage:
        page = await self.repository.get_page(organization_id, resource_id, page_number)
        if not page:
            raise HTTPException(status_code=404, detail="Page not found")
        return page



