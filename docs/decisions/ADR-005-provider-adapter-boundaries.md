# ADR 005: Provider Adapter Boundaries

## Context
Integrating with external AI and storage providers.

## Decision
Use strict adapter patterns to isolate vendor SDKs.

## Consequences
Easy to swap providers.

## Alternatives Considered
Direct SDK usage in business logic (rejected due to coupling).

## Status
Accepted
