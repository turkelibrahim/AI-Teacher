from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from typing import List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.db.session import get_db_session
from app.api.deps import RequireOrganizationPermission, get_current_active_user
from app.modules.identity.models import User
from app.modules.lesson.schemas import LessonCreate, LessonResponse, MessageCreate, MessageResponse
from app.modules.lesson.service import LessonService

logger = logging.getLogger("canli_ogretmen.lesson.router")

router = APIRouter()

@router.post("/{organization_id}/lessons", response_model=LessonResponse)
async def create_lesson(
    organization_id: UUID,
    request: LessonCreate,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_active_user),
    membership = Depends(RequireOrganizationPermission("resource.read"))
):
    service = LessonService(db)
    return await service.create_lesson(organization_id, user.id, request)


@router.get("/{organization_id}/lessons", response_model=List[LessonResponse])
async def list_lessons(
    organization_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    membership = Depends(RequireOrganizationPermission("resource.read"))
):
    service = LessonService(db)
    return await service.list_lessons(organization_id)


@router.get("/{organization_id}/lessons/{lesson_id}", response_model=LessonResponse)
async def get_lesson(
    organization_id: UUID,
    lesson_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    membership = Depends(RequireOrganizationPermission("resource.read"))
):
    service = LessonService(db)
    return await service.get_lesson(organization_id, lesson_id)


@router.get("/{organization_id}/lessons/{lesson_id}/messages", response_model=List[MessageResponse])
async def get_lesson_messages(
    organization_id: UUID,
    lesson_id: UUID,
    db: AsyncSession = Depends(get_db_session),
    membership = Depends(RequireOrganizationPermission("resource.read"))
):
    service = LessonService(db)
    return await service.get_messages(organization_id, lesson_id)


@router.post("/{organization_id}/lessons/{lesson_id}/messages", response_model=MessageResponse)
async def add_message(
    organization_id: UUID,
    lesson_id: UUID,
    request: MessageCreate,
    db: AsyncSession = Depends(get_db_session),
    membership = Depends(RequireOrganizationPermission("resource.read"))
):
    service = LessonService(db)
    return await service.add_message_and_generate_response(organization_id, lesson_id, request)


@router.post("/{organization_id}/lessons/{lesson_id}/messages/stream")
async def stream_message(
    organization_id: UUID,
    lesson_id: UUID,
    request: MessageCreate,
    db: AsyncSession = Depends(get_db_session),
    membership = Depends(RequireOrganizationPermission("resource.read"))
):
    service = LessonService(db)
    return StreamingResponse(
        service.stream_message_and_generate_response(organization_id, lesson_id, request),
        media_type="text/event-stream"
    )
