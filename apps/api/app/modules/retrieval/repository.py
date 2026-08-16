from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from uuid import UUID

from app.modules.retrieval.models import ResourceChunk, ResourceIndexingJob

class RetrievalRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def search_chunks(
        self,
        organization_id: UUID,
        query_embedding: List[float],
        resource_ids: Optional[List[UUID]] = None,
        top_k: int = 5,
        score_threshold: Optional[float] = None
    ) -> List[Tuple[ResourceChunk, float]]:
        
        # We use cosine distance (1 - cosine_similarity)
        # the `<=>` operator in pgvector computes cosine distance
        distance_col = ResourceChunk.embedding.cosine_distance(query_embedding).label("distance")
        
        stmt = select(ResourceChunk, distance_col).where(
            ResourceChunk.organization_id == organization_id
        )
        
        if resource_ids:
            stmt = stmt.where(ResourceChunk.resource_id.in_(resource_ids))
            
        if score_threshold is not None:
            max_distance = 1.0 - score_threshold
            stmt = stmt.where(distance_col <= max_distance)
            
        stmt = stmt.order_by(distance_col, ResourceChunk.chunk_index).limit(top_k)
        
        result = await self.db.execute(stmt)
        rows = result.all()
        
        # Convert distance back to similarity score (score = 1 - distance)
        return [(row[0], 1.0 - row[1]) for row in rows]

    async def create_indexing_job(self, job: ResourceIndexingJob) -> ResourceIndexingJob:
        self.db.add(job)
        await self.db.flush()
        return job

    async def get_indexing_job(self, job_id: UUID, organization_id: UUID) -> Optional[ResourceIndexingJob]:
        stmt = select(ResourceIndexingJob).where(
            ResourceIndexingJob.id == job_id,
            ResourceIndexingJob.organization_id == organization_id
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()
        
    async def get_latest_completed_indexing_job(self, ingestion_job_id: UUID) -> Optional[ResourceIndexingJob]:
        stmt = select(ResourceIndexingJob).where(
            ResourceIndexingJob.ingestion_job_id == ingestion_job_id,
            ResourceIndexingJob.status == "COMPLETED"
        ).order_by(desc(ResourceIndexingJob.completed_at))
        result = await self.db.execute(stmt)
        return result.scalars().first()
