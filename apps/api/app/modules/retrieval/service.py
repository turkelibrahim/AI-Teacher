from uuid import UUID
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
import logging
import asyncio

from app.modules.retrieval.repository import RetrievalRepository
from app.modules.retrieval.embeddings import get_embedding_provider
from app.modules.retrieval.schemas import SearchRequest, SearchResponse, SearchResultChunk
from app.core.config import settings

logger = logging.getLogger("canli_ogretmen.retrieval.service")

class RetrievalService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = RetrievalRepository(db)
        self.provider = get_embedding_provider()

    async def search(
        self,
        organization_id: UUID,
        request: SearchRequest
    ) -> SearchResponse:
        query_text = request.query.strip()
        if not query_text:
            raise HTTPException(status_code=400, detail="Query cannot be empty")
        
        # Guard against extremely long queries to prevent DOS
        if len(query_text) > 2000:
            raise HTTPException(status_code=400, detail="Query is too long")

        try:
            query_embedding = await asyncio.to_thread(self.provider.embed_query, query_text)
        except Exception as e:
            logger.error(f"Failed to embed query: {e}")
            raise HTTPException(status_code=500, detail="Failed to process query embedding")

        chunks_with_scores = await self.repo.search_chunks(
            organization_id=organization_id,
            query_embedding=query_embedding,
            resource_ids=request.resource_ids,
            top_k=request.top_k,
            score_threshold=request.score_threshold
        )

        results = []
        for chunk, score in chunks_with_scores:
            results.append(SearchResultChunk(
                chunk_id=chunk.id,
                resource_id=chunk.resource_id,
                page_number=chunk.page_number,
                chunk_index=chunk.chunk_index,
                text=chunk.text,
                score=score
            ))

        return SearchResponse(
            query=query_text,
            results=results
        )
