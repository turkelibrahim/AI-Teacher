from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.db.session import get_db_session
from app.core.redis import get_redis
from app.core.storage import get_storage
import logging

router = APIRouter(tags=["Health"])
logger = logging.getLogger("canli_ogretmen")

@router.get("/health")
@router.get("/health/live")
async def health_live():
    return {"status": "ok"}

@router.get("/health/ready")
async def health_ready(db: AsyncSession = Depends(get_db_session)):
    services = {
        "api": "ok",
        "postgres": "unknown",
        "redis": "unknown",
        "object_storage": "unknown"
    }
    
    # Check Postgres
    try:
        await db.execute(text("SELECT 1"))
        services["postgres"] = "ok"
    except Exception as e:
        logger.error(f"Postgres health check failed: {e}")
        services["postgres"] = "error"

    # Check Redis
    try:
        redis = await get_redis()
        await redis.ping()
        services["redis"] = "ok"
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        services["redis"] = "error"

    # Check Object Storage
    try:
        storage = await get_storage()
        storage_ok = await storage.healthcheck()
        if storage_ok:
            services["object_storage"] = "ok"
        else:
            services["object_storage"] = "error"
    except Exception as e:
        logger.error(f"Object Storage health check failed: {e}")
        services["object_storage"] = "error"

    status = "ok" if all(v == "ok" for v in services.values()) else "error"
    
    return {
        "status": status,
        "services": services
    }
