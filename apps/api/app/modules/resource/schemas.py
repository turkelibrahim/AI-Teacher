from pydantic import BaseModel, UUID4, Field
from datetime import datetime
from typing import Optional

class ResourceBase(BaseModel):
    original_filename: str = Field(..., max_length=255)
    display_name: Optional[str] = Field(None, max_length=255)

class ResourceCreate(ResourceBase):
    pass

class ResourceUpdate(BaseModel):
    display_name: Optional[str] = Field(None, max_length=255)

class ResourceResponse(ResourceBase):
    id: UUID4
    organization_id: UUID4
    uploaded_by_user_id: Optional[UUID4]
    
    content_type: str
    extension: str
    size_bytes: int
    sha256: str
    status: str
    
    created_at: datetime
    updated_at: datetime
    
    model_config = {"from_attributes": True}

class PresignedUrlResponse(BaseModel):
    url: str
    expires_in: int
