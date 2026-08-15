# ADR 003: Object Storage for Files

## Context
Storing user uploads (PDFs, docs) and media.

## Decision
Use S3-compatible object storage (MinIO for local).

## Consequences
Decoupled storage, scalable.

## Alternatives Considered
Database BLOBs (rejected due to size limits and performance).

## Status
Accepted
