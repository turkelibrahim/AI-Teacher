from fastapi import UploadFile, HTTPException
from app.modules.resource.repository import ResourceRepository
from app.modules.resource.models import Resource
from app.modules.identity.models import AuditLog
from app.core.storage import get_storage
from app.core.config import settings
import uuid
import hashlib
import os
import magic
import zipfile
import tempfile
from sqlalchemy.ext.asyncio import AsyncSession
import logging

logger = logging.getLogger("canli_ogretmen")

class ResourceService:
    def __init__(self, repo: ResourceRepository, db_session: AsyncSession):
        self.repo = repo
        self.db_session = db_session

    def _validate_docx(self, file_path: str):
        try:
            with zipfile.ZipFile(file_path, 'r') as zf:
                namelist = zf.namelist()
                if '[Content_Types].xml' not in namelist:
                    return False
                if not any(name.startswith('word/') for name in namelist):
                    return False
            return True
        except zipfile.BadZipFile:
            return False

    def _validate_pptx(self, file_path: str):
        try:
            with zipfile.ZipFile(file_path, 'r') as zf:
                namelist = zf.namelist()
                if '[Content_Types].xml' not in namelist:
                    return False
                if not any(name.startswith('ppt/') for name in namelist):
                    return False
            return True
        except zipfile.BadZipFile:
            return False

    async def _log_audit(self, event_type: str, organization_id: uuid.UUID, user_id: uuid.UUID, resource_id: uuid.UUID, size_bytes: int, content_type: str):
        log = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            event_type=event_type,
            entity_type="RESOURCE",
            entity_id=str(resource_id),
            metadata_={
                "size_bytes": size_bytes,
                "content_type": content_type
            }
        )
        self.db_session.add(log)

    async def upload_resource(self, organization_id: uuid.UUID, user_id: uuid.UUID, file: UploadFile) -> Resource:
        if not file.filename:
            raise HTTPException(status_code=400, detail="Filename missing")
            
        # Filename Security
        original_filename = os.path.basename(file.filename.replace("\\", "/"))
        _, ext = os.path.splitext(original_filename)
        ext = ext.lower()
        
        if ext not in settings.ALLOWED_UPLOAD_EXTENSIONS:
            raise HTTPException(status_code=400, detail=f"Extension {ext} not allowed")

        # Streaming upload to bounded temp file
        size_bytes = 0
        max_size = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        sha256_hash = hashlib.sha256()
        
        fd, temp_path = tempfile.mkstemp()
        try:
            with os.fdopen(fd, 'wb') as tmp:
                while True:
                    chunk = await file.read(65536)
                    if not chunk:
                        break
                    size_bytes += len(chunk)
                    if size_bytes > max_size:
                        raise HTTPException(status_code=400, detail="File too large")
                    sha256_hash.update(chunk)
                    tmp.write(chunk)
            
            if size_bytes == 0:
                raise HTTPException(status_code=400, detail="File is empty")
                
            sha256 = sha256_hash.hexdigest()
            
            # Validation via python-magic
            mime = magic.Magic(mime=True)
            detected_mime = mime.from_file(temp_path)
            
            if "application/x-dosexec" in detected_mime or "application/x-executable" in detected_mime or ext in [".exe", ".dll", ".bat", ".sh", ".cmd", ".ps1"]:
                raise HTTPException(status_code=400, detail="Executable files are forbidden")

            # PDF Validation
            if ext == ".pdf":
                with open(temp_path, 'rb') as f:
                    header = f.read(4)
                    if header != b"%PDF":
                        raise HTTPException(status_code=400, detail="Invalid PDF file")
            
            # DOCX Validation
            elif ext == ".docx":
                if not self._validate_docx(temp_path):
                    raise HTTPException(status_code=400, detail="Invalid DOCX file")
            
            # PPTX Validation
            elif ext == ".pptx":
                if not self._validate_pptx(temp_path):
                    raise HTTPException(status_code=400, detail="Invalid PPTX file")

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
                with open(temp_path, 'rb') as tmp:
                    await storage.put(storage_key, tmp, size_bytes, content_type=detected_mime, bucket_name=settings.RESOURCE_BUCKET_NAME)
            except Exception as e:
                logger.error(f"Storage upload failed: {e}")
                # Log audit event for failure directly
                try:
                    await self._log_audit("RESOURCE_UPLOAD_FAILED", organization_id, user_id, resource_id, size_bytes, detected_mime)
                    await self.db_session.commit()
                except Exception:
                    await self.db_session.rollback()
                raise HTTPException(status_code=500, detail="Failed to upload to storage")
                
            try:
                await self.repo.create(resource)
                await self._log_audit("RESOURCE_UPLOADED", organization_id, user_id, resource_id, size_bytes, detected_mime)
                await self.db_session.commit()
                await self.db_session.refresh(resource)
                return resource
            except Exception as e:
                await self.db_session.rollback()
                try:
                    await storage.delete(storage_key, bucket_name=settings.RESOURCE_BUCKET_NAME)
                except Exception as e_comp:
                    logger.error(f"Compensation failed for {storage_key}: {e_comp}")
                raise HTTPException(status_code=500, detail="Database transaction failed")

        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    async def get_download_url(self, organization_id: uuid.UUID, resource_id: uuid.UUID, user_id: uuid.UUID = None) -> str:
        resource = await self.repo.get_by_id(organization_id, resource_id)
        if not resource:
            raise HTTPException(status_code=404, detail="Resource not found")
            
        storage = await get_storage()
        url = await storage.get_presigned_url(resource.storage_key, expires_in=settings.PRESIGNED_URL_EXPIRE_SECONDS, bucket_name=resource.storage_bucket)
        
        # Log download audit event
        if user_id:
            await self._log_audit("RESOURCE_DOWNLOADED", organization_id, user_id, resource_id, resource.size_bytes, resource.content_type)
            await self.db_session.commit()
            
        return url

    async def delete_resource(self, organization_id: uuid.UUID, resource_id: uuid.UUID, user_id: uuid.UUID = None):
        resource = await self.repo.get_by_id(organization_id, resource_id)
        if not resource:
            raise HTTPException(status_code=404, detail="Resource not found")
            
        # Hard delete in Storage FIRST to prevent false success
        storage = await get_storage()
        try:
            await storage.delete(resource.storage_key, bucket_name=resource.storage_bucket)
        except Exception as e:
            logger.error(f"Storage deletion failed for {resource.storage_key}: {e}")
            raise HTTPException(status_code=500, detail="Storage deletion failed. Delete aborted.")

        # Soft delete in DB
        await self.repo.soft_delete(resource)
        if user_id:
            await self._log_audit("RESOURCE_DELETED", organization_id, user_id, resource_id, resource.size_bytes, resource.content_type)
        await self.db_session.commit()
