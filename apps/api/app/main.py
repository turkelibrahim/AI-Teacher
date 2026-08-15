from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.core.config import settings
from app.core.logging import setup_logging, CorrelationIdMiddleware
from app.core.exceptions import global_exception_handler, BaseAPIException
from app.core.redis import init_redis, close_redis
from app.core.storage import get_storage
from app.api.v1.health import router as health_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Setup
    setup_logging()
    logger = logging.getLogger("canli_ogretmen")
    logger.info("Starting up Canlı Öğretmen AI API...")
    
    # Initialize Redis
    await init_redis()
    logger.info("Redis initialized.")
    
    # Initialize Object Storage
    storage = await get_storage()
    try:
        await storage.initialize()
        logger.info("Object Storage initialized.")
    except Exception as e:
        logger.error(f"Failed to initialize Object Storage: {e}")
    
    yield
    
    # Teardown
    await close_redis()
    logger.info("Shutting down...")

app = FastAPI(
    title=settings.APP_NAME,
    lifespan=lifespan,
    debug=settings.APP_DEBUG
)

app.add_middleware(CorrelationIdMiddleware)

if settings.get_cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.get_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.add_exception_handler(Exception, global_exception_handler)
app.add_exception_handler(BaseAPIException, global_exception_handler)

app.include_router(health_router, prefix="/api/v1")
app.include_router(health_router) # also at root for easy access
