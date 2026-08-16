from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Any
from datetime import datetime
import uuid

class IngestionJobResponse(BaseModel):
    id: uuid.UUID
    resource_id: uuid.UUID
    status: str
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    page_count: Optional[int] = None
    character_count: Optional[int] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class StartIngestionRequest(BaseModel):
    force: bool = False

class ResourceDocumentResponse(BaseModel):
    id: uuid.UUID
    resource_id: uuid.UUID
    ingestion_job_id: uuid.UUID
    title: Optional[str] = None
    language: Optional[str] = None
    total_pages: Optional[int] = None
    total_characters: Optional[int] = None
    plain_text: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ResourcePageResponse(BaseModel):
    id: uuid.UUID
    resource_id: uuid.UUID
    page_number: int
    page_label: Optional[str] = None
    text: str
    character_count: int
    metadata_: Optional[dict] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

class PaginatedPagesResponse(BaseModel):
    items: List[ResourcePageResponse]
    total: int
    limit: int
    offset: int

class PaginatedIngestionJobResponse(BaseModel):
    items: List[IngestionJobResponse]
    total: int
    limit: int
    offset: int

