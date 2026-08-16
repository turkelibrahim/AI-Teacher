import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, JSON, Text, Index
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import Vector

from app.db.base import Base

class ResourceIndexingJob(Base):
    __tablename__ = "resource_indexing_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    resource_id = Column(UUID(as_uuid=True), ForeignKey("resources.id", ondelete="CASCADE"), nullable=False)
    ingestion_job_id = Column(UUID(as_uuid=True), ForeignKey("resource_ingestion_jobs.id", ondelete="CASCADE"), nullable=False)
    requested_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)

    status = Column(String, nullable=False, default="PENDING")

    embedding_model = Column(String, nullable=False)
    embedding_dimension = Column(Integer, nullable=False)

    chunk_target_tokens = Column(Integer, nullable=False)
    chunk_overlap_tokens = Column(Integer, nullable=False)

    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    failed_at = Column(DateTime(timezone=True), nullable=True)

    error_code = Column(String, nullable=True)
    error_message = Column(String, nullable=True)

    total_chunks = Column(Integer, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index('ix_resource_indexing_jobs_org_res', 'organization_id', 'resource_id'),
        Index('ix_resource_indexing_jobs_status', 'status'),
    )


class ResourceChunk(Base):
    __tablename__ = "resource_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    resource_id = Column(UUID(as_uuid=True), ForeignKey("resources.id", ondelete="CASCADE"), nullable=False)
    ingestion_job_id = Column(UUID(as_uuid=True), ForeignKey("resource_ingestion_jobs.id", ondelete="CASCADE"), nullable=False)
    indexing_job_id = Column(UUID(as_uuid=True), ForeignKey("resource_indexing_jobs.id", ondelete="CASCADE"), nullable=False)
    resource_page_id = Column(UUID(as_uuid=True), ForeignKey("resource_pages.id", ondelete="CASCADE"), nullable=True)

    chunk_index = Column(Integer, nullable=False)

    page_number = Column(Integer, nullable=True)
    page_label = Column(String, nullable=True)

    text = Column(Text, nullable=False)

    character_count = Column(Integer, nullable=False)
    token_count = Column(Integer, nullable=True)

    # pgvector embedding column. We use the hardcoded dimension 384 for the model in Phase 5.
    embedding = Column(Vector(384), nullable=False)

    embedding_model = Column(String, nullable=False)
    embedding_dimension = Column(Integer, nullable=False)

    content_sha256 = Column(String, nullable=False)

    metadata_ = Column("metadata", JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index('ix_resource_chunks_org', 'organization_id'),
        Index('ix_resource_chunks_res', 'resource_id'),
        Index('ix_resource_chunks_indexing', 'indexing_job_id'),
        Index('ix_resource_chunks_content_sha', 'content_sha256'),
    )

