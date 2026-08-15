# Current State

## Architecture
- Modular monolith pattern initialized for the backend.
- FastAPI backend with standard directories (core, api, modules, db, workers).
- Async SQLAlchemy setup for PostgreSQL.
- Celery worker structure setup for async tasks.
- Redis integrated for state/broker.
- MinIO integrated for S3-compatible object storage.

## Frontend
- Next.js 14+ with App Router.
- Basic UI connecting to /api/v1/health/ready.
- Containerized development setup running alongside backend.

## Infrastructure
- Canonical Project Root established at C:\Projects\ai-teacher.
- Docker Compose defines the following services correctly:
  - api
  - worker
  - web
  - postgres
  - redis
  - minio
- .env and docker-compose.yml are securely aligned.





