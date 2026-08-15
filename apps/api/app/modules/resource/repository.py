from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update
from app.modules.resource.models import Resource
from app.modules.resource.schemas import ResourceCreate
import uuid

class ResourceRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, organization_id: uuid.UUID, resource_id: uuid.UUID) -> Resource | None:
        result = await self.session.execute(
            select(Resource).where(
                Resource.id == resource_id,
                Resource.organization_id == organization_id,
                Resource.deleted_at.is_(None)
            )
        )
        return result.scalars().first()

    async def list_by_organization(self, organization_id: uuid.UUID) -> list[Resource]:
        result = await self.session.execute(
            select(Resource).where(
                Resource.organization_id == organization_id,
                Resource.deleted_at.is_(None)
            ).order_by(Resource.created_at.desc())
        )
        return list(result.scalars().all())

    async def create(self, resource: Resource) -> Resource:
        self.session.add(resource)
        await self.session.flush()
        return resource

    async def update_status(self, resource_id: uuid.UUID, status: str) -> None:
        await self.session.execute(
            update(Resource).where(Resource.id == resource_id).values(status=status)
        )
        await self.session.flush()

    async def soft_delete(self, resource: Resource) -> None:
        from sqlalchemy.sql import func
        resource.deleted_at = func.now()
        resource.status = "DELETED"
        await self.session.flush()

    async def hard_delete(self, resource: Resource) -> None:
        await self.session.delete(resource)
        await self.session.flush()
