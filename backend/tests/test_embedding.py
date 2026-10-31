import math

from backend.app.services.embedding import (
    EmbeddingService,
    _generate_deterministic_pseudo_vector,
)


def test_deterministic_pseudo_vector_properties() -> None:
    vec1 = _generate_deterministic_pseudo_vector("Hello world", dim=768)
    vec2 = _generate_deterministic_pseudo_vector("Hello world", dim=768)
    vec3 = _generate_deterministic_pseudo_vector("Different text", dim=768)

    assert len(vec1) == 768
    # Determinism: same input generates identical vector
    assert vec1 == vec2
    # Different input generates different vector
    assert vec1 != vec3

    # Check vector is approximately unit-normalized (L2 norm == 1.0)
    norm = math.sqrt(sum(x * x for x in vec1))
    assert math.isclose(norm, 1.0, rel_tol=1e-5)


def test_embed_texts_and_query() -> None:
    service = EmbeddingService(dimensions=768, batch_size=2)
    texts = ["Invoice 101", "Payment details", "Contract agreement", "Terms of service"]
    embeddings = service.embed_texts(texts)

    assert len(embeddings) == 4
    for emb in embeddings:
        assert len(emb) == 768

    query_emb = service.embed_query("Invoice 101")
    assert len(query_emb) == 768
    # In offline mode, embedding "Invoice 101" matches query embedding
    assert query_emb == embeddings[0]


def test_embed_empty_texts() -> None:
    service = EmbeddingService()
    assert service.embed_texts([]) == []
