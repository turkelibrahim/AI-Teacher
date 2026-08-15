from minio import Minio
from app.core.config import settings
import asyncio

class ObjectStorage:
    def __init__(self):
        self.client = Minio(
            settings.S3_ENDPOINT,
            access_key=settings.S3_ACCESS_KEY,
            secret_key=settings.S3_SECRET_KEY,
            secure=settings.S3_SECURE
        )
        
    async def _run_in_executor(self, func, *args, **kwargs):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: func(*args, **kwargs))

    async def initialize(self):
        # Create bucket if it doesn't exist
        exists = await self._run_in_executor(self.client.bucket_exists, settings.S3_BUCKET)
        if not exists:
            await self._run_in_executor(self.client.make_bucket, settings.S3_BUCKET)

    async def put(self, object_name: str, data, length: int, content_type: str = "application/octet-stream"):
        return await self._run_in_executor(
            self.client.put_object,
            settings.S3_BUCKET,
            object_name,
            data,
            length,
            content_type=content_type
        )

    async def get(self, object_name: str):
        return await self._run_in_executor(
            self.client.get_object,
            settings.S3_BUCKET,
            object_name
        )

    async def delete(self, object_name: str):
        return await self._run_in_executor(
            self.client.remove_object,
            settings.S3_BUCKET,
            object_name
        )

    async def healthcheck(self):
        try:
            # Just listing buckets is a good health check
            await self._run_in_executor(self.client.list_buckets)
            return True
        except Exception as e:
            return False

storage_client = ObjectStorage()

async def get_storage():
    return storage_client
