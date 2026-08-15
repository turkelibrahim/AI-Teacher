from fastapi import UploadFile, HTTPException
from app.modules.resource.repository import ResourceRepository
from app.modules.resource.models import Resource
from app.core.storage import get_storage
from app.core.config import settings
import uuid
import hashlib
import os
import magic
from sqlalchemy.ext.asyncio import AsyncSession
import logging

logger = logging.getLogger("canli_ogretmen")

class ResourceService:
    def __init__(self, repo: ResourceRepository, db_session: AsyncSession):
        self.repo = repo
        self.db_session = db_session

    async def upload_resource(self, organization_id: uuid.UUID, user_id: uuid.UUID, file: UploadFile) -> Resource:
        # File Validation
        if not file.filename:
            raise HTTPException(status_code=400, detail="Filename missing")
            
        # Secure filename logic
        original_filename = os.path.basename(file.filename)
        _, ext = os.path.splitext(original_filename)
        ext = ext.lower()
        
        if ext not in settings.ALLOWED_UPLOAD_EXTENSIONS:
            raise HTTPException(status_code=400, detail=f"Extension {ext} not allowed")

        # Read content and calculate hash + size
        content = await file.read()
        size_bytes = len(content)
        
        if size_bytes > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File too large")
        if size_bytes == 0:
            raise HTTPException(status_code=400, detail="File is empty")
            
        sha256 = hashlib.sha256(content).hexdigest()
        
        # Magic bytes detection
        mime = magic.Magic(mime=True)
        detected_mime = mime.from_buffer(content[:2048])
        
        # We enforce basic checks for executables
        if "application/x-dosexec" in detected_mime or "application/x-executable" in detected_mime or ext in [".exe", ".dll", ".bat", ".sh", ".cmd"]:
            raise HTTPException(status_code=400, detail="Executable files are forbidden")

        resource_id = uuid.uuid4()
        storage_key = f"organizations/{organization_id}/resources/{resource_id}/original/{resource_id}{ext}"
        
        resource = Resource(
            id=resource_id,
            organization_id=organization_id,
            uploaded_by_user_id=user_id,
            original_filename=original_filename,
            display_name=original_filename,
            storage_bucket=settings.RESOURCE_BUCKET_NAME,
            storage_key=storage_key,
            content_type=detected_mime,
            extension=ext,
            size_bytes=size_bytes,
            sha256=sha256,
            status="UPLOADED"
        )
        
        storage = await get_storage()
        
        try:
            # Upload to MinIO using io.BytesIO
            import io
            file_obj = io.BytesIO(content)
            await storage.put(storage_key, file_obj, size_bytes, content_type=detected_mime)
        except Exception as e:
            logger.error(f"Storage upload failed: {e}")
            raise HTTPException(status_code=500, detail="Failed to upload to storage")
            
        try:
            await self.repo.create(resource)
            await self.db_session.commit()
            await self.db_session.refresh(resource)
            return resource
        except Exception as e:
            await self.db_session.rollback()
            # Compensation: delete orphaned object
            try:
                await storage.delete(storage_key)
            except Exception as e_comp:
                logger.error(f"Compensation failed for {storage_key}: {e_comp}")
            raise HTTPException(status_code=500, detail="Database transaction failed")

    async def get_download_url(self, organization_id: uuid.UUID, resource_id: uuid.UUID) -> str:
        resource = await self.repo.get_by_id(organization_id, resource_id)
        if not resource:
            raise HTTPException(status_code=404, detail="Resource not found")
            
        storage = await get_storage()
        url = await storage.get_presigned_url(resource.storage_key, expires_in=settings.PRESIGNED_URL_EXPIRE_SECONDS)
        return url

    async def delete_resource(self, organization_id: uuid.UUID, resource_id: uuid.UUID):
        resource = await self.repo.get_by_id(organization_id, resource_id)
        if not resource:
            raise HTTPException(status_code=404, detail="Resource not found")
            
        # Soft delete in DB
        await self.repo.soft_delete(resource)
        await self.db_session.commit()
        
        # Hard delete in Storage
        try:
            storage = await get_storage()
            await storage.delete(resource.storage_key)
        except Exception as e:
            logger.error(f"Storage deletion failed for {resource.storage_key}: {e}")
            # Keep soft-deleted state, don't rollback so we don't expose it again,
            # but note it in logs.
