import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, JSON, Text, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base

class ResourceIngestionJob(Base):
    __tablename__ = "resource_ingestion_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    resource_id = Column(UUID(as_uuid=True), ForeignKey("resources.id", ondelete="CASCADE"), nullable=False)
    requested_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)

    status = Column(String, nullable=False, default="PENDING")

    extractor = Column(String, nullable=True)
    extractor_version = Column(String, nullable=True)

    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    failed_at = Column(DateTime(timezone=True), nullable=True)

    error_code = Column(String, nullable=True)
    error_message = Column(String, nullable=True)

    page_count = Column(Integer, nullable=True)
    character_count = Column(Integer, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index('ix_resource_ingestion_jobs_org_res', 'organization_id', 'resource_id'),
        Index('ix_resource_ingestion_jobs_status', 'status'),
    )


class ResourceDocument(Base):
    __tablename__ = "resource_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    resource_id = Column(UUID(as_uuid=True), ForeignKey("resources.id", ondelete="CASCADE"), nullable=False)
    ingestion_job_id = Column(UUID(as_uuid=True), ForeignKey("resource_ingestion_jobs.id", ondelete="RESTRICT"), nullable=False)
    
    title = Column(String, nullable=True)
    language = Column(String, nullable=True)
    total_pages = Column(Integer, nullable=True)
    total_characters = Column(Integer, nullable=True)
    plain_text = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    __table_args__ = (
        Index('ix_resource_documents_org_res', 'organization_id', 'resource_id'),
    )


class ResourcePage(Base):
    __tablename__ = "resource_pages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    resource_id = Column(UUID(as_uuid=True), ForeignKey("resources.id", ondelete="CASCADE"), nullable=False)
    ingestion_job_id = Column(UUID(as_uuid=True), ForeignKey("resource_ingestion_jobs.id", ondelete="RESTRICT"), nullable=False)

    page_number = Column(Integer, nullable=False)
    page_label = Column(String, nullable=True)

    text = Column(Text, nullable=False)
    character_count = Column(Integer, nullable=False)

    metadata_ = Column("metadata", JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index('ix_resource_pages_org_res', 'organization_id', 'resource_id'),
        Index('ix_resource_pages_job', 'ingestion_job_id'),
    )


