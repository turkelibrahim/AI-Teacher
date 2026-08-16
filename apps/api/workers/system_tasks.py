import asyncio
import uuid
import logging
import tempfile
import traceback
from workers.app import celery_app
from celery.exceptions import Retry
from app.core.storage import ObjectStorage
from app.modules.ingestion.repository import IngestionRepository
from app.modules.resource.repository import ResourceRepository
from app.modules.ingestion.extractors import get_extractor
from app.modules.ingestion.extractors.errors import (
    ExtractionError, CorruptedDocumentError, EncryptedDocumentError,
    OcrRequiredError, LimitExceededError, ZipBombError, UnsupportedFormatError
)
from app.modules.ingestion.models import ResourceDocument, ResourcePage
from app.modules.organization.models import Organization, OrganizationMember
from app.modules.identity.models import User, Role, Permission, AuditLog
from app.modules.resource.models import Resource
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker
from app.core.config import settings

logger = logging.getLogger(__name__)

# These error codes are PERMANENT — do not retry
PERMANENT_ERROR_CODES = {
    "CORRUPTED_DOCUMENT",
    "ENCRYPTED_PDF",
    "OCR_REQUIRED",
    "PAGE_LIMIT_EXCEEDED",
    "TEXT_LIMIT_EXCEEDED",
    "ZIP_LIMIT_EXCEEDED",
    "UNSUPPORTED_FORMAT",
}

async def _run_extraction(job_id: str, is_last_attempt: bool = False):
    storage = ObjectStorage()
    job_uuid = uuid.UUID(job_id)

    engine = create_async_engine(
        settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
        poolclass=NullPool
    )
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session() as session:
        repo = IngestionRepository(session)
        resource_repo = ResourceRepository(session)

        job = await repo.claim_job(job_uuid)
        if not job:
            logger.warning(f"Job {job_id} could not be claimed or not QUEUED.")
            await engine.dispose()
            return

        audit_log = AuditLog(
            organization_id=job.organization_id,
            user_id=job.requested_by_user_id,
            event_type="INGESTION_STARTED",
            entity_type="RESOURCE_INGESTION_JOB",
            entity_id=str(job.id)
        )
        session.add(audit_log)
        await session.commit()

        try:
            resource = await resource_repo.get_by_id(job.organization_id, job.resource_id)
            if not resource:
                raise CorruptedDocumentError("Resource not found in storage")

            await repo.cleanup_failed_job_data(job_uuid)

            with tempfile.NamedTemporaryFile() as tmp:
                minio_response = await storage.get(resource.storage_key, bucket_name=resource.storage_bucket)
                for chunk in minio_response.stream(32 * 1024):
                    tmp.write(chunk)
                tmp.flush()
                tmp.seek(0)
                minio_response.close()
                minio_response.release_conn()

                extractor = get_extractor(resource.content_type, resource.original_filename)
                extracted_doc = extractor.extract(tmp)

            doc_model = ResourceDocument(
                organization_id=job.organization_id,
                resource_id=job.resource_id,
                ingestion_job_id=job.id,
                title=extracted_doc.title,
                language=extracted_doc.language,
                total_pages=extracted_doc.total_pages,
                total_characters=extracted_doc.total_characters,
                plain_text=extracted_doc.plain_text
            )
            await repo.create_document(doc_model)

            pages = []
            for p in extracted_doc.pages:
                pages.append(ResourcePage(
                    organization_id=job.organization_id,
                    resource_id=job.resource_id,
                    ingestion_job_id=job.id,
                    page_number=p.page_number,
                    page_label=p.page_label,
                    text=p.text,
                    character_count=p.character_count,
                    metadata_=p.metadata
                ))
            await repo.create_pages(pages)

            from datetime import datetime, timezone
            await repo.update_job_status(
                job.id,
                "COMPLETED",
                page_count=extracted_doc.total_pages,
                character_count=extracted_doc.total_characters,
                extractor=extractor.__class__.__name__,
                completed_at=datetime.now(timezone.utc)
            )

            audit_log_complete = AuditLog(
                organization_id=job.organization_id,
                user_id=job.requested_by_user_id,
                event_type="INGESTION_COMPLETED",
                entity_type="RESOURCE_INGESTION_JOB",
                entity_id=str(job.id)
            )
            session.add(audit_log_complete)
            await session.commit()

        except ExtractionError as e:
            logger.error(f"Extraction error for job {job_id}: {e}")
            await session.rollback()
            if e.code in PERMANENT_ERROR_CODES or is_last_attempt:
                from datetime import datetime, timezone
                await repo.update_job_status(job_uuid, "FAILED", error_code=e.code, error_message=str(e), failed_at=datetime.now(timezone.utc))

                audit_log_fail = AuditLog(
                    organization_id=job.organization_id,
                    user_id=job.requested_by_user_id,
                    event_type="INGESTION_FAILED",
                    entity_type="RESOURCE_INGESTION_JOB",
                    entity_id=str(job.id)
                )
                session.add(audit_log_fail)
                await session.commit()
            else:
                await repo.update_job_status(job_uuid, "QUEUED")
                await session.commit()
            # Re-raise so Celery knows result; permanent errors won't be retried
            raise

        except Exception as e:
            logger.exception(f"Unexpected extraction failure for job {job_id}")
            await session.rollback()
            if is_last_attempt:
                from datetime import datetime, timezone
                await repo.update_job_status(
                    job_uuid, "FAILED",
                    error_code="EXTRACTION_FAILED",
                    error_message="An unexpected error occurred during extraction",
                    failed_at=datetime.now(timezone.utc)
                )

                audit_log_fail = AuditLog(
                    organization_id=job.organization_id,
                    user_id=job.requested_by_user_id,
                    event_type="INGESTION_FAILED",
                    entity_type="RESOURCE_INGESTION_JOB",
                    entity_id=str(job.id)
                )
                session.add(audit_log_fail)
                await session.commit()
            else:
                await repo.update_job_status(job_uuid, "QUEUED")
                await session.commit()
            raise

        finally:
            await engine.dispose()


@celery_app.task(
    name="system.process_resource_ingestion",
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    acks_late=True
)
def process_resource_ingestion(self, job_id: str):
    """
    Celery task: extract a resource document.

    Retry policy:
    - Transient failures (DB/MinIO connectivity, unexpected errors): retry up to 3 times.
    - Permanent failures (CORRUPTED_DOCUMENT, ENCRYPTED_PDF, OCR_REQUIRED, etc.): do NOT retry.
    """
    is_last_attempt = self.request.retries >= self.max_retries
    try:
        asyncio.run(_run_extraction(job_id, is_last_attempt))
    except ExtractionError as e:
        # Permanent errors — do not retry
        if e.code in PERMANENT_ERROR_CODES:
            logger.warning(f"Permanent extraction failure for job {job_id}: {e.code} — not retrying")
            return
        # Transient extraction error — retry
        logger.warning(f"Transient extraction error for job {job_id}: {e.code} — scheduling retry")
        raise self.retry(exc=e)
    except Exception as e:
        # Unexpected error — retry up to max_retries
        logger.warning(f"Transient failure for job {job_id}: {e} — scheduling retry")
        raise self.retry(exc=e)


