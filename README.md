# Canlı Öğretmen AI

A scalable SaaS platform for AI-powered interactive tutoring.

## Architecture
Modular monolith + workers.
- **Backend:** FastAPI, PostgreSQL (pgvector), Redis, MinIO, Celery.
- **Frontend:** Next.js (React).

## Requirements
- Docker
- Docker Compose
- Git

## Quick Start
1. Clone the repository.
2. Copy environment variables:
   ```bash
   cp .env.example .env
   ```
3. Start the services:
   ```bash
   docker compose up --build -d
   ```

## URLs
- **Frontend:** http://localhost:3000
- **API:** http://localhost:8000/api/v1
- **API docs:** http://localhost:8000/docs
- **MinIO console:** http://localhost:9001 (minioadmin / minioadmin)

## Health Check
- Live: `curl http://localhost:8000/api/v1/health/live`
- Ready: `curl http://localhost:8000/api/v1/health/ready`

## Tests
To run tests locally (requires python env):
```bash
cd apps/api
pytest
```

## Project Structure
```text
apps/
  api/      # Backend FastAPI application
  web/      # Frontend Next.js application
docs/       # Architecture decisions, status, runbooks
evidence/   # Execution and test proofs
infra/      # Infrastructure configurations (docker, nginx)
packages/   # Shared code and contracts
scripts/    # Utility scripts
```
