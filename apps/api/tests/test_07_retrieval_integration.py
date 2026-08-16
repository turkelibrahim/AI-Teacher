import pytest
import asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.retrieval.models import ResourceIndexingJob, ResourceChunk
from sqlalchemy import select
import time

pytestmark = pytest.mark.asyncio

async def test_real_semantic_search_integration(client: AsyncClient, setup_tenants):
    try:
        token_a, user_a_id, org_id, token_b, org_b_id = setup_tenants
        auth_headers = {"Authorization": f"Bearer {token_a}"}

        # 1. Upload a deterministic test document
        doc_content = """Page 1:
The capital of France is Paris.

Page 2:
Photosynthesis occurs primarily in chloroplasts.

Page 3:
Saturn is a gas giant with a prominent ring system.
"""
        file_upload = {"file": ("facts.txt", doc_content.encode("utf-8"), "text/plain")}
        resp = await client.post(
            f"/api/v1/organizations/{org_id}/resources",
            headers=auth_headers,
            files=file_upload
        )
        print(f"UPLOAD RESPONSE: {resp.status_code} - {resp.text}", flush=True)
        assert resp.status_code == 200, f"Upload failed: {resp.text}"
        resource_data = resp.json()
        resource_id = resource_data["id"]

        # Trigger ingestion
        resp = await client.post(
            f"/api/v1/organizations/{org_id}/resources/{resource_id}/ingestions",
            headers=auth_headers,
            json={"force": False}
        )
        print(f"INGESTION RESPONSE: {resp.status_code} - {resp.text}", flush=True)
        assert resp.status_code == 202, f"Ingestion failed: {resp.text}"
        ingestion_job_id = resp.json()["id"]

        # Wait for ingestion and indexing to complete via Celery workers
        # We poll the search endpoint until results are found, which means indexing is done.
        for _ in range(15):
            await asyncio.sleep(3)
            search_resp = await client.post(
                f"/api/v1/organizations/{org_id}/retrieval/search",
                headers=auth_headers,
                json={
                    "query": "Where does photosynthesis occur?",
                    "top_k": 3
                }
            )
            if search_resp.status_code == 200 and len(search_resp.json()["results"]) > 0:
                break
        else:
            assert False, "Indexing did not complete in time (polled for 45 seconds)"
        assert search_resp.status_code == 200, f"Search failed: {search_resp.text}"
        results = search_resp.json()["results"]
        assert len(results) > 0
        top_result = results[0]
        assert "chloroplasts" in top_result["text"].lower()

        # Verify Tenant Isolation: User B in Org B should not find it
        auth_headers_b = {"Authorization": f"Bearer {token_b}"}
        search_resp_b = await client.post(
            f"/api/v1/organizations/{org_b_id}/retrieval/search",
            headers=auth_headers_b,
            json={
                "query": "Where does photosynthesis occur?",
                "top_k": 3
            }
        )
        assert search_resp_b.status_code == 200
        assert len(search_resp_b.json()["results"]) == 0
    except Exception as e:
        print(f"CRITICAL TEST EXCEPTION: {e}", flush=True)
        import traceback
        traceback.print_exc()
        raise e
