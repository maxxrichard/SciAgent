import numpy as np

from sciagent.retrieval import Document, HashingEmbedder, InMemoryVectorStore, PgVectorStore


def test_embeddings_are_normalised_and_deterministic():
    e = HashingEmbedder(64)
    a, b = e.embed("kaplan meier survival"), e.embed("kaplan meier survival")
    assert np.allclose(a, b) and np.isclose(np.linalg.norm(a), 1.0)
    assert not e.embed("").any()


def test_search_ranks_relevant_document_first():
    store = InMemoryVectorStore()
    assert store.search("anything") == []
    store.upsert(
        [
            Document("1", "Kaplan-Meier survival analysis by treatment arm"),
            Document("2", "Nucleus segmentation for microscopy images"),
            Document("3", "Variant annotation for whole genome sequencing"),
        ]
    )
    hits = store.search("segment nuclei in microscopy", k=2)
    assert len(store) == 3 and hits[0][0].id == "2" and len(hits) == 2


def test_pgvector_store_rejects_unsafe_table_names():
    import pytest

    with pytest.raises(ValueError):
        PgVectorStore(None, HashingEmbedder(), table="x; DROP TABLE y")  # type: ignore[arg-type]
