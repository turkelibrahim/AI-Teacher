from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc
from uuid import UUID
from typing import List, Optional

from app.modules.lesson.models import Lesson, LessonMessage
from app.modules.lesson.schemas import LessonCreate

class LessonRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_lesson(self, organization_id: UUID, user_id: UUID, lesson_in: LessonCreate) -> Lesson:
        db_lesson = Lesson(
            organization_id=organization_id,
            created_by_user_id=user_id,
            title=lesson_in.title
        )
        self.db.add(db_lesson)
        await self.db.commit()
        await self.db.refresh(db_lesson)
        return db_lesson

    async def get_lesson_by_id_and_org(self, lesson_id: UUID, organization_id: UUID) -> Optional[Lesson]:
        stmt = select(Lesson).where(
            Lesson.id == lesson_id,
            Lesson.organization_id == organization_id
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def list_lessons_by_org(self, organization_id: UUID) -> List[Lesson]:
        stmt = select(Lesson).where(
            Lesson.organization_id == organization_id
        ).order_by(desc(Lesson.created_at))
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def add_message(self, lesson_id: UUID, role: str, content: str, context_sources: Optional[list] = None) -> LessonMessage:
        message = LessonMessage(
            lesson_id=lesson_id,
            role=role,
            content=content,
            context_sources=context_sources
        )
        self.db.add(message)
        await self.db.commit()
        await self.db.refresh(message)
        return message

    async def get_messages_for_lesson(self, lesson_id: UUID) -> List[LessonMessage]:
        stmt = select(LessonMessage).where(
            LessonMessage.lesson_id == lesson_id
        ).order_by(LessonMessage.created_at)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
