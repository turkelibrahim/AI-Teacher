from pydantic import BaseModel, ConfigDict
from typing import List, Optional, Any
from datetime import datetime
from uuid import UUID

class LessonCreate(BaseModel):
    title: str

class LessonResponse(BaseModel):
    id: UUID
    organization_id: UUID
    created_by_user_id: Optional[UUID]
    title: str
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class MessageCreate(BaseModel):
    content: str

class MessageResponse(BaseModel):
    id: UUID
    lesson_id: UUID
    role: str
    content: str
    context_sources: Optional[List[dict]] = None
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
