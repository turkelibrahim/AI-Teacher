import pytest
import uuid
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.lesson.models import Lesson, LessonMessage
from app.ai.prompt import build_prompt_messages
from app.ai.llm import get_llm_provider, MockLLMProvider

def test_prompt_builder():
    context_chunks = ["The Earth is round.", "Water boils at 100 degrees Celsius."]
    chat_history = [{"role": "user", "content": "Hello!"}, {"role": "assistant", "content": "Hi there."}]
    user_question = "What shape is the Earth?"
    
    messages = build_prompt_messages(context_chunks, chat_history, user_question)
    
    assert messages[0]["role"] == "system"
    assert "You are an AI Teaching Assistant" in messages[0]["content"]
    
    assert messages[1]["role"] == "user"
    assert messages[1]["content"] == "Hello!"
    
    assert messages[2]["role"] == "assistant"
    assert messages[2]["content"] == "Hi there."
    
    assert messages[3]["role"] == "user"
    assert "The Earth is round." in messages[3]["content"]
    assert "What shape is the Earth?" in messages[3]["content"]

def test_mock_llm_provider():
    provider = get_llm_provider(mock=True)
    assert isinstance(provider, MockLLMProvider)

@pytest.mark.asyncio
async def test_create_lesson(client: AsyncClient, setup_tenants):
    token_a, _, org_a_id, _, _ = setup_tenants
    response = await client.post(
        f"/api/v1/organizations/{org_a_id}/lessons",
        json={"title": "Test Lesson"},
        headers={"Authorization": f"Bearer {token_a}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Test Lesson"
    assert "id" in data

@pytest.mark.asyncio
async def test_tenant_isolation_lesson_read(client: AsyncClient, setup_tenants):
    token_a, _, org_a_id, token_b, org_b_id = setup_tenants
    
    # Org1 creates lesson
    res = await client.post(
        f"/api/v1/organizations/{org_a_id}/lessons",
        json={"title": "Org1 Lesson"},
        headers={"Authorization": f"Bearer {token_a}"}
    )
    lesson_id = res.json()["id"]

    # Org2 tries to access Org1's lesson using Org2's ID
    res2 = await client.get(
        f"/api/v1/organizations/{org_b_id}/lessons/{lesson_id}",
        headers={"Authorization": f"Bearer {token_b}"}
    )
    assert res2.status_code == 404

from unittest.mock import patch, Mock

@pytest.mark.asyncio
async def test_lesson_message_flow(client: AsyncClient, setup_tenants):
    token_a, _, org_a_id, _, _ = setup_tenants
    
    # Mock retrieval service to not actually need the DB/pgvector data
    with patch('app.modules.retrieval.service.RetrievalService.search') as mock_search, \
         patch('app.modules.lesson.service.get_llm_provider') as mock_llm:
        
        mock_search.return_value = Mock(results=[
            Mock(text="Mocked context chunk", chunk_id=uuid.uuid4(), resource_id=uuid.uuid4(), score=0.99)
        ])
        
        from app.ai.llm import MockLLMProvider
        mock_llm.return_value = MockLLMProvider()
        
        # Create lesson
        res = await client.post(
            f"/api/v1/organizations/{org_a_id}/lessons",
            json={"title": "Physics 101"},
            headers={"Authorization": f"Bearer {token_a}"}
        )
        lesson_id = res.json()["id"]
        
        # Add message
        res_msg = await client.post(
            f"/api/v1/organizations/{org_a_id}/lessons/{lesson_id}/messages",
            json={"content": "What is gravity?"},
            headers={"Authorization": f"Bearer {token_a}"}
        )
        assert res_msg.status_code == 200
        data = res_msg.json()
        assert data["role"] == "assistant"
        assert data["content"] == "This is a mocked response based on your context."
        assert len(data["context_sources"]) == 1

@pytest.mark.asyncio
async def test_lesson_streaming_flow(client: AsyncClient, setup_tenants):
    token_a, _, org_a_id, _, _ = setup_tenants
    
    with patch('app.modules.retrieval.service.RetrievalService.search') as mock_search, \
         patch('app.modules.lesson.service.get_llm_provider') as mock_llm:
        
        mock_search.return_value = Mock(results=[])
        
        from app.ai.llm import MockLLMProvider
        mock_llm.return_value = MockLLMProvider()
        
        # Create lesson
        res = await client.post(
            f"/api/v1/organizations/{org_a_id}/lessons",
            json={"title": "Streaming Test"},
            headers={"Authorization": f"Bearer {token_a}"}
        )
        lesson_id = res.json()["id"]
        
        # Add message stream
        res_msg = await client.post(
            f"/api/v1/organizations/{org_a_id}/lessons/{lesson_id}/messages/stream",
            json={"content": "Stream me"},
            headers={"Authorization": f"Bearer {token_a}"}
        )
        assert res_msg.status_code == 200
        assert res_msg.headers["content-type"] == "text/event-stream; charset=utf-8"
        
        # The content should be SSE format
        content = res_msg.text
        assert "data: " in content
        assert "This " in content
        assert "is a " in content
        assert "mocked stream." in content
        assert "done" in content

@pytest.mark.asyncio
async def test_add_message_unauthorized(client: AsyncClient, setup_tenants):
    token_a, _, org_a_id, _, _ = setup_tenants
    res_msg = await client.post(
        f"/api/v1/organizations/{org_a_id}/lessons/{uuid.uuid4()}/messages",
        json={"content": "Hello"},
        headers={"Authorization": f"Bearer invalid_token"}
    )
    assert res_msg.status_code == 401
