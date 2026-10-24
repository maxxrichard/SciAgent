# ADR-0007: PostgreSQL + pgvector for retrieval

- **Status:** Accepted
- **Date:** 2026-02-17

## Context
The agent retrieves dataset descriptions and tool documentation (tens of thousands of
documents, not billions). We already run PostgreSQL for the catalog, runs and audit log.

## Decision
Store embeddings in a pgvector table with an HNSW index (cosine distance) in the same RDS
instance. Locally and in tests, an in-memory store implements the same interface.

## Consequences
- No additional stateful service to operate; transactional consistency with the catalog.
- Retrieval scales comfortably for our corpus; revisit if it grows by orders of magnitude.
