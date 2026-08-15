# ADR 002: PostgreSQL as Source of Truth

## Context
Need a robust relational database for the main application state and future pgvector usage.

## Decision
Use PostgreSQL.

## Consequences
Strong ACID compliance and vector support.

## Alternatives Considered
MongoDB (rejected due to relational needs), MySQL (lacks robust native vector support like pgvector).

## Status
Accepted
