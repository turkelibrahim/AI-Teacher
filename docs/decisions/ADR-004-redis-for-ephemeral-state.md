# ADR 004: Redis for Ephemeral State

## Context
Need a fast cache and message broker for Celery.

## Decision
Use Redis.

## Consequences
High performance for temporary data.

## Alternatives Considered
RabbitMQ (rejected as Redis can do both cache and broker).

## Status
Accepted
