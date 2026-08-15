# ADR 006: Worker Architecture

## Context
Heavy AI and ingestion tasks.

## Decision
Use Celery workers with Redis broker.

## Consequences
Asynchronous processing independent of API.

## Alternatives Considered
BackgroundTasks in FastAPI (rejected due to durability issues).

## Status
Accepted
