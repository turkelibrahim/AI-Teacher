from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import AnyHttpUrl, validator

class Settings(BaseSettings):
    APP_NAME: str = "Canlı Öğretmen AI"
    APP_ENV: str = "development"
    APP_DEBUG: bool = True

    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    POSTGRES_HOST: str
    POSTGRES_PORT: str
    POSTGRES_DB: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str

    DATABASE_URL: str

    REDIS_HOST: str
    REDIS_PORT: str
    REDIS_URL: str

    S3_ENDPOINT: str
    S3_ACCESS_KEY: str
    S3_SECRET_KEY: str
    S3_BUCKET: str
    S3_REGION: str
    S3_SECURE: bool = False

    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str

    CORS_ALLOWED_ORIGINS: str = ""

    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    PASSWORD_MIN_LENGTH: int = 8
    LOGIN_RATE_LIMIT: int = 5
    LOGIN_RATE_LIMIT_WINDOW: int = 300
    COOKIE_SECURE: bool = False
    COOKIE_SAMESITE: str = "lax"

    @validator("JWT_SECRET_KEY")
    def validate_jwt_secret(cls, v, values):
        env = values.get("APP_ENV", "development")
        if env == "production" and (v == "unsafe-secret-for-dev" or len(v) < 32):
            raise ValueError("JWT_SECRET_KEY must be a secure random string in production")
        return v

    @property
    def get_cors_origins(self) -> List[str]:
        if not self.CORS_ALLOWED_ORIGINS:
            return []
        return [origin.strip() for origin in self.CORS_ALLOWED_ORIGINS.split(",") if origin.strip()]

    
    # Resource Settings
    RESOURCE_BUCKET_NAME: str = "ai-teacher-resources"
    MAX_UPLOAD_SIZE_MB: int = 50
    PRESIGNED_URL_EXPIRE_SECONDS: int = 3600
    ALLOWED_UPLOAD_EXTENSIONS: list[str] = [".pdf", ".docx", ".pptx", ".txt", ".md"]

    # Ingestion & Extraction Limits
    MAX_INGESTION_PAGES: int = 1000
    MAX_EXTRACTED_CHARACTERS: int = 5000000
    MAX_OFFICE_ENTRIES: int = 10000
    MAX_OFFICE_UNCOMPRESSED_BYTES: int = 50 * 1024 * 1024
    MAX_SINGLE_ENTRY_UNCOMPRESSED_BYTES: int = 10 * 1024 * 1024

    # Retrieval & RAG
    EMBEDDING_PROVIDER: str = "sentence-transformers"
    EMBEDDING_MODEL: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    EMBEDDING_DIMENSION: int = 384
    EMBEDDING_DEVICE: str = "cpu"
    EMBEDDING_BATCH_SIZE: int = 16

    CHUNK_TARGET_TOKENS: int = 96
    CHUNK_OVERLAP_TOKENS: int = 16
    CHUNK_MAX_TOKENS: int = 112
    CHUNK_MIN_TOKENS: int = 24

    RETRIEVAL_TOP_K: int = 5

    # LLM & Lesson Engine
    LLM_API_KEY: str = "sk-dummy"
    LLM_BASE_URL: str = "http://localhost:11434/v1"
    LLM_MODEL_NAME: str = "llama3"
    LLM_TIMEOUT: int = 60
    LLM_MAX_TOKENS: int = 1024
    LLM_TEMPERATURE: float = 0.7

    model_config = SettingsConfigDict(env_file=(".env", "../../.env"), env_file_encoding="utf-8", extra="ignore")

settings = Settings()








