from sqlalchemy import Column, String, Integer, ForeignKey, DateTime, BigInteger
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from app.db.base import Base

class Resource(Base):
    __tablename__ = "resources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    uploaded_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    original_filename = Column(String(255), nullable=False)
    display_name = Column(String(255), nullable=True)
    
    storage_bucket = Column(String(255), nullable=False)
    storage_key = Column(String(1024), nullable=False, unique=True)
    
    content_type = Column(String(255), nullable=False)
    extension = Column(String(32), nullable=False)
    size_bytes = Column(BigInteger, nullable=False)
    sha256 = Column(String(64), nullable=False)
    
    status = Column(String(64), nullable=False, default="UPLOADED") # UPLOADED, FAILED, DELETED

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

