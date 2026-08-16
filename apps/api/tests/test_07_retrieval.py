import pytest
import asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.organization.models import Organization
from app.modules.identity.models import User
from app.modules.resource.models import Resource
from app.modules.retrieval.models import ResourceIndexingJob, ResourceChunk
from app.modules.retrieval.embeddings import LocalEmbeddingProvider
from app.modules.retrieval.chunking import SemanticChunker

pytestmark = pytest.mark.asyncio
from sqlalchemy import select
import json
import uuid

pytestmark = pytest.mark.asyncio

async def test_chunking_logic():
    chunker = SemanticChunker(target_tokens=10, max_tokens=20, overlap_tokens=2)
    text = "This is a short paragraph.\n\nThis is another paragraph."
    chunks = chunker.chunk_text(text)
    assert len(chunks) >= 1
    assert "paragraph" in chunks[0]

async def test_embedding_provider():
    provider = LocalEmbeddingProvider()
    emb = provider.embed_query("Hello world")
    assert len(emb) == 384
    
    embs = provider.embed_documents(["First", "Second"])
    assert len(embs) == 2
    assert len(embs[0]) == 384

async def _wait_for_indexing(db: AsyncSession, org_id: uuid.UUID, resource_id: uuid.UUID):
    for _ in range(20):
        await asyncio.sleep(1)
        await db.rollback() # clear session cache
        stmt = select(ResourceIndexingJob).where(
            ResourceIndexingJob.resource_id == resource_id,
            ResourceIndexingJob.organization_id == org_id
        )
        job = (await db.execute(stmt)).scalars().first()
        if job and job.status == "COMPLETED":
            return job
        if job and job.status == "FAILED":
            raise Exception("Indexing failed")
