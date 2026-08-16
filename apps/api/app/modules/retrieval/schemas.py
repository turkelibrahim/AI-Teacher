from pydantic import BaseModel, Field, UUID4
from typing import List, Optional
from datetime import datetime

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    resource_ids: Optional[List[UUID4]] = None
    top_k: int = Field(5, ge=1, le=50)
    score_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)

class SearchResultChunk(BaseModel):
    chunk_id: UUID4
    resource_id: UUID4
    page_number: Optional[int] = None
    chunk_index: int
    text: str
    score: float

class SearchResponse(BaseModel):
    query: str
    results: List[SearchResultChunk]

class IndexingJobResponse(BaseModel):
    id: UUID4
    resource_id: UUID4
    status: str
    total_chunks: Optional[int]
    created_at: datetime
    error_message: Optional[str]
