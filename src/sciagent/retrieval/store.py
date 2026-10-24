"""Vector stores: in-memory (numpy) and PostgreSQL + pgvector."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

import numpy as np
from sqlalchemy import Engine, text

from sciagent.retrieval.embeddings import HashingEmbedder


@dataclass(frozen=True)
class Document:
    id: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


class VectorStore(Protocol):
    def upsert(self, docs: list[Document]) -> None: ...

    def search(self, query: str, k: int = 4) -> list[tuple[Document, float]]: ...


class InMemoryVectorStore:
    def __init__(self, embedder: HashingEmbedder | None = None) -> None:
        self.embedder = embedder or HashingEmbedder()
        self._docs: dict[str, Document] = {}
        self._vecs: dict[str, np.ndarray] = {}

    def __len__(self) -> int:
        return len(self._docs)

    def upsert(self, docs: list[Document]) -> None:
        for d in docs:
            self._docs[d.id] = d
            self._vecs[d.id] = self.embedder.embed(d.text)

    def search(self, query: str, k: int = 4) -> list[tuple[Document, float]]:
        if not self._docs:
            return []
        ids = list(self._docs)
        mat = np.stack([self._vecs[i] for i in ids])
        scores = mat @ self.embedder.embed(query)
        top = np.argsort(-scores)[:k]
        return [(self._docs[ids[i]], float(scores[i])) for i in top]


class PgVectorStore:
    """pgvector-backed store using cosine distance (``<=>``) and an HNSW index."""

    def __init__(self, engine: Engine, embedder: HashingEmbedder, table: str = "embeddings"):
        if not table.isidentifier():
            raise ValueError("invalid table name")
        self.engine, self.embedder, self.table = engine, embedder, table

    def create_schema(self) -> None:  # pragma: no cover - requires PostgreSQL
        with self.engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.execute(
                text(
                    f"CREATE TABLE IF NOT EXISTS {self.table} ("
                    "id text PRIMARY KEY, body text NOT NULL, metadata jsonb NOT NULL, "
                    f"embedding vector({self.embedder.dim}) NOT NULL)"
                )
            )
            conn.execute(
                text(
                    f"CREATE INDEX IF NOT EXISTS {self.table}_hnsw ON {self.table} "
                    "USING hnsw (embedding vector_cosine_ops)"
                )
            )

    def upsert(self, docs: list[Document]) -> None:  # pragma: no cover - requires PostgreSQL
        import json

        with self.engine.begin() as conn:
            for d in docs:
                conn.execute(
                    text(
                        f"INSERT INTO {self.table} (id, body, metadata, embedding) "
                        "VALUES (:id, :body, CAST(:meta AS jsonb), CAST(:emb AS vector)) "
                        "ON CONFLICT (id) DO UPDATE SET body = EXCLUDED.body, "
                        "metadata = EXCLUDED.metadata, embedding = EXCLUDED.embedding"
                    ),
                    {
                        "id": d.id,
                        "body": d.text,
                        "meta": json.dumps(d.metadata),
                        "emb": str(self.embedder.embed(d.text).tolist()),
                    },
                )

    def search(self, query: str, k: int = 4) -> list[tuple[Document, float]]:  # pragma: no cover
        emb = str(self.embedder.embed(query).tolist())
        with self.engine.connect() as conn:
            rows = conn.execute(
                text(
                    f"SELECT id, body, metadata, 1 - (embedding <=> CAST(:emb AS vector)) AS score "
                    f"FROM {self.table} ORDER BY embedding <=> CAST(:emb AS vector) LIMIT :k"
                ),
                {"emb": emb, "k": k},
            )
            return [(Document(r.id, r.body, r.metadata), float(r.score)) for r in rows]
