from uuid import UUID
from typing import List, AsyncGenerator
import json
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
import logging

from app.modules.lesson.repository import LessonRepository
from app.modules.lesson.schemas import LessonCreate, LessonResponse, MessageCreate, MessageResponse
from app.modules.retrieval.service import RetrievalService
from app.modules.retrieval.schemas import SearchRequest
from app.ai.llm import get_llm_provider
from app.ai.prompt import build_prompt_messages

logger = logging.getLogger("canli_ogretmen.lesson.service")

class LessonService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = LessonRepository(db)
        self.retrieval_service = RetrievalService(db)
        self.llm_provider = get_llm_provider()

    async def create_lesson(self, organization_id: UUID, user_id: UUID, request: LessonCreate) -> LessonResponse:
        lesson = await self.repo.create_lesson(organization_id, user_id, request)
        return LessonResponse.model_validate(lesson)

    async def get_lesson(self, organization_id: UUID, lesson_id: UUID) -> LessonResponse:
        lesson = await self.repo.get_lesson_by_id_and_org(lesson_id, organization_id)
        if not lesson:
            raise HTTPException(status_code=404, detail="Lesson not found or access denied")
        return LessonResponse.model_validate(lesson)

    async def list_lessons(self, organization_id: UUID) -> List[LessonResponse]:
        lessons = await self.repo.list_lessons_by_org(organization_id)
        return [LessonResponse.model_validate(l) for l in lessons]

    async def get_messages(self, organization_id: UUID, lesson_id: UUID) -> List[MessageResponse]:
        # Enforce tenant isolation first
        lesson = await self.repo.get_lesson_by_id_and_org(lesson_id, organization_id)
        if not lesson:
            raise HTTPException(status_code=404, detail="Lesson not found or access denied")
            
        messages = await self.repo.get_messages_for_lesson(lesson_id)
        return [MessageResponse.model_validate(m) for m in messages]

    async def add_message_and_generate_response(self, organization_id: UUID, lesson_id: UUID, request: MessageCreate) -> MessageResponse:
        # 1. Enforce tenant isolation
        lesson = await self.repo.get_lesson_by_id_and_org(lesson_id, organization_id)
        if not lesson:
            raise HTTPException(status_code=404, detail="Lesson not found or access denied")

        # 2. Save User Message
        user_msg = await self.repo.add_message(lesson_id, role="user", content=request.content)
        
        # 3. Retrieve Context
        try:
            search_request = SearchRequest(query=request.content, top_k=5)
            search_response = await self.retrieval_service.search(organization_id, search_request)
            context_chunks = [result.text for result in search_response.results]
            context_sources = [
                {"chunk_id": str(r.chunk_id), "resource_id": str(r.resource_id), "score": r.score}
                for r in search_response.results
            ]
        except Exception as e:
            logger.error(f"Retrieval failed for lesson {lesson_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to retrieve context")

        # 4. Fetch Chat History
        db_messages = await self.repo.get_messages_for_lesson(lesson_id)
        # Exclude the very last user message we just saved so it doesn't appear twice
        chat_history = [{"role": m.role, "content": m.content} for m in db_messages[:-1]]

        # 5. Build Prompt
        messages = build_prompt_messages(context_chunks, chat_history, request.content)

        # 6. Call LLM
        try:
            ai_response_content = await self.llm_provider.generate_response(messages)
        except Exception as e:
            logger.error(f"LLM generation failed for lesson {lesson_id}: {e}")
            raise HTTPException(status_code=502, detail="AI provider is unavailable")

        # 7. Save Assistant Message
        assistant_msg = await self.repo.add_message(
            lesson_id=lesson_id, 
            role="assistant", 
            content=ai_response_content,
            context_sources=context_sources
        )

        return MessageResponse.model_validate(assistant_msg)

    async def stream_message_and_generate_response(
        self, organization_id: UUID, lesson_id: UUID, request: MessageCreate
    ) -> AsyncGenerator[str, None]:
        # 1. Enforce tenant isolation
        lesson = await self.repo.get_lesson_by_id_and_org(lesson_id, organization_id)
        if not lesson:
            yield f"data: {json.dumps({'error': 'Lesson not found or access denied'})}\n\n"
            return

        # 2. Save User Message
        await self.repo.add_message(lesson_id, role="user", content=request.content)
        
        # 3. Retrieve Context
        try:
            search_request = SearchRequest(query=request.content, top_k=5)
            search_response = await self.retrieval_service.search(organization_id, search_request)
            context_chunks = [result.text for result in search_response.results]
            context_sources = [
                {"chunk_id": str(r.chunk_id), "resource_id": str(r.resource_id), "score": r.score}
                for r in search_response.results
            ]
        except Exception as e:
            logger.error(f"Retrieval failed for lesson {lesson_id}: {e}")
            yield f"data: {json.dumps({'error': 'Failed to retrieve context'})}\n\n"
            return

        # 4. Fetch Chat History
        db_messages = await self.repo.get_messages_for_lesson(lesson_id)
        chat_history = [{"role": m.role, "content": m.content} for m in db_messages[:-1]]

        # 5. Build Prompt
        messages = build_prompt_messages(context_chunks, chat_history, request.content)

        # 6. Stream from LLM
        full_content = ""
        try:
            async for chunk in self.llm_provider.generate_stream(messages):
                full_content += chunk
                yield f"data: {json.dumps({'content': chunk})}\n\n"
        except Exception as e:
            logger.error(f"LLM streaming failed for lesson {lesson_id}: {e}")
            yield f"data: {json.dumps({'error': 'AI provider stream failed'})}\n\n"
            return

        # 7. Save Assistant Message after stream ends
        try:
            await self.repo.add_message(
                lesson_id=lesson_id, 
                role="assistant", 
                content=full_content,
                context_sources=context_sources
            )
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as e:
            logger.error(f"Failed to save assistant message for lesson {lesson_id}: {e}")
