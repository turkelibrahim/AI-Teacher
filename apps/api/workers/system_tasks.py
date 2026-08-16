import asyncio
import logging
import tempfile
import uuid
from celery import Celery
from workers.app import celery_app
from app.core.storage import ObjectStorage
from app.modules.ingestion.repository import IngestionRepository
from app.modules.resource.repository import ResourceRepository
from app.modules.ingestion.extractors import get_extractor
from app.modules.ingestion.extractors.errors import (
    ExtractionError, CorruptedDocumentError,
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

# These error codes are PERMANENT - do not retry
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
            
            # Phase 5: Automatically queue an indexing job upon ingestion completion
            process_resource_indexing.delay(str(job.id), str(job.organization_id))

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
    is_last_attempt = self.request.retries >= self.max_retries
    try:
        asyncio.run(_run_extraction(job_id, is_last_attempt))
    except ExtractionError as e:
        if e.code in PERMANENT_ERROR_CODES:
            logger.warning(f"Permanent extraction failure for job {job_id}: {e.code} - not retrying")
            return
        logger.warning(f"Transient extraction error for job {job_id}: {e.code} - scheduling retry")
        raise self.retry(exc=e)
    except Exception as e:
        logger.warning(f"Transient failure for job {job_id}: {e} - scheduling retry")
        raise self.retry(exc=e)


async def _run_indexing(ingestion_job_id: str, organization_id: str, is_last_attempt: bool = False):
    from app.modules.retrieval.models import ResourceIndexingJob, ResourceChunk
    from app.modules.retrieval.chunking import SemanticChunker
    from app.modules.retrieval.embeddings import get_embedding_provider
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import NullPool
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from sqlalchemy import select
    from datetime import datetime, timezone
    import uuid
    import hashlib

    job_uuid = uuid.UUID(ingestion_job_id)
    org_uuid = uuid.UUID(organization_id)

    engine = create_async_engine(
        settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
        poolclass=NullPool
    )
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    
    provider = get_embedding_provider()
    chunker = SemanticChunker(
        target_tokens=settings.CHUNK_TARGET_TOKENS,
        max_tokens=settings.CHUNK_MAX_TOKENS,
        overlap_tokens=settings.CHUNK_OVERLAP_TOKENS
    )

    async with async_session() as session:
        # Check if already successfully indexed
        stmt = select(ResourceIndexingJob).where(
            ResourceIndexingJob.ingestion_job_id == job_uuid,
            ResourceIndexingJob.status == "COMPLETED"
        )
        existing = await session.execute(stmt)
        if existing.scalars().first():
            logger.info(f"Ingestion {ingestion_job_id} already indexed successfully.")
            await engine.dispose()
            return

        # Fetch ingestion job and pages
        from app.modules.ingestion.models import ResourceIngestionJob, ResourcePage
        stmt = select(ResourceIngestionJob).where(ResourceIngestionJob.id == job_uuid)
        result = await session.execute(stmt)
        ingestion_job = result.scalars().first()
        if not ingestion_job:
            await engine.dispose()
            return
            
        indexing_job = ResourceIndexingJob(
            organization_id=org_uuid,
            resource_id=ingestion_job.resource_id,
            ingestion_job_id=job_uuid,
            requested_by_user_id=ingestion_job.requested_by_user_id,
            status="PROCESSING",
            embedding_model=settings.EMBEDDING_MODEL,
            embedding_dimension=settings.EMBEDDING_DIMENSION,
            chunk_target_tokens=settings.CHUNK_TARGET_TOKENS,
            chunk_overlap_tokens=settings.CHUNK_OVERLAP_TOKENS,
            started_at=datetime.now(timezone.utc)
        )
        session.add(indexing_job)
        await session.flush()
        
        try:
            stmt = select(ResourcePage).where(
                ResourcePage.ingestion_job_id == job_uuid
            ).order_by(ResourcePage.page_number)
            pages = (await session.execute(stmt)).scalars().all()
            
            all_chunks = []
            chunk_index = 0
            
            for page in pages:
                texts = chunker.chunk_text(page.text)
                for t in texts:
                    if not t.strip():
                        continue
                    tokens = chunker.get_token_count(t)
                    content_sha = hashlib.sha256(t.encode('utf-8')).hexdigest()
                    
                    chunk = ResourceChunk(
                        organization_id=org_uuid,
                        resource_id=ingestion_job.resource_id,
                        ingestion_job_id=job_uuid,
                        indexing_job_id=indexing_job.id,
                        resource_page_id=page.id,
                        chunk_index=chunk_index,
                        page_number=page.page_number,
                        page_label=page.page_label,
                        text=t,
                        character_count=len(t),
                        token_count=tokens,
                        embedding=None, # will fill later
                        embedding_model=settings.EMBEDDING_MODEL,
                        embedding_dimension=settings.EMBEDDING_DIMENSION,
                        content_sha256=content_sha
                    )
                    all_chunks.append(chunk)
                    chunk_index += 1
                    
            if all_chunks:
                # batch embed
                texts_to_embed = [c.text for c in all_chunks]
                embeddings = provider.embed_documents(texts_to_embed)
                
                for c, emb in zip(all_chunks, embeddings):
                    c.embedding = emb
                    session.add(c)
                    
            indexing_job.status = "COMPLETED"
            indexing_job.total_chunks = len(all_chunks)
            indexing_job.completed_at = datetime.now(timezone.utc)
            await session.commit()
            
            audit_log_complete = AuditLog(
                organization_id=org_uuid,
                user_id=ingestion_job.requested_by_user_id,
                event_type="INDEXING_COMPLETED",
                entity_type="RESOURCE_INDEXING_JOB",
                entity_id=str(indexing_job.id)
            )
            session.add(audit_log_complete)
            await session.commit()
            
        except Exception as e:
            logger.error(f"Indexing failure: {e}")
            await session.rollback()
            if is_last_attempt:
                indexing_job.status = "FAILED"
                indexing_job.error_message = str(e)
                indexing_job.failed_at = datetime.now(timezone.utc)
                session.add(indexing_job)
                
                audit_log_fail = AuditLog(
                    organization_id=org_uuid,
                    user_id=ingestion_job.requested_by_user_id,
                    event_type="INDEXING_FAILED",
                    entity_type="RESOURCE_INDEXING_JOB",
                    entity_id=str(indexing_job.id)
                )
                session.add(audit_log_fail)
                
                await session.commit()
            raise
        finally:
            await engine.dispose()

@celery_app.task(
    name="system.process_resource_indexing",
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    acks_late=True
)
def process_resource_indexing(self, ingestion_job_id: str, organization_id: str):
    is_last_attempt = self.request.retries >= self.max_retries
    try:
        import asyncio
        asyncio.run(_run_indexing(ingestion_job_id, organization_id, is_last_attempt))
    except Exception as e:
        logger.warning(f"Transient failure for indexing job {ingestion_job_id}: {e} - scheduling retry")
        raise self.retry(exc=e)

