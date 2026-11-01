import uuid
from unittest.mock import AsyncMock

import pytest

from backend.app.services.retrieval import (
    RetrievalFilter,
    RetrievalService,
    RetrievalStrategy,
    RetrievedChunk,
)


def _create_mock_chunk(
    chunk_id: uuid.UUID,
    doc_id: uuid.UUID,
    content: str,
    score: float,
    match_type: str,
) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        document_id=doc_id,
        page_number=1,
        chunk_index=0,
        chunk_type="text",
        content=content,
        score=score,
        match_type=match_type,
        metadata_json={},
    )


def test_reciprocal_rank_fusion_single_list() -> None:
    doc_id = uuid.uuid4()
    c1 = _create_mock_chunk(uuid.uuid4(), doc_id, "Chunk 1", 0.9, "vector")
    c2 = _create_mock_chunk(uuid.uuid4(), doc_id, "Chunk 2", 0.8, "vector")

    merged = RetrievalService.reciprocal_rank_fusion([[c1, c2]], k=60)

    assert len(merged) == 2
    # Rank 0 (1-based: 1) -> 1 / (60 + 1) = 1/61
    expected_score_c1 = round(1.0 / 61.0, 6)
    expected_score_c2 = round(1.0 / 62.0, 6)
    assert merged[0].chunk_id == c1.chunk_id
    assert merged[0].score == expected_score_c1
    assert merged[0].match_type == "hybrid"
    assert merged[1].chunk_id == c2.chunk_id
    assert merged[1].score == expected_score_c2


def test_reciprocal_rank_fusion_overlap_boost() -> None:
    doc_id = uuid.uuid4()
    cid_overlap = uuid.uuid4()
    cid_vec_only = uuid.uuid4()
    cid_kw_only = uuid.uuid4()

    c_overlap_vec = _create_mock_chunk(cid_overlap, doc_id, "Both Match", 0.85, "vector")
    c_vec_only = _create_mock_chunk(cid_vec_only, doc_id, "Vector Only", 0.95, "vector")

    c_kw_only = _create_mock_chunk(cid_kw_only, doc_id, "Keyword Only", 1.2, "keyword")
    c_overlap_kw = _create_mock_chunk(cid_overlap, doc_id, "Both Match", 0.9, "keyword")

    # Vector list: c_vec_only (rank 1), c_overlap_vec (rank 2)
    # Keyword list: c_kw_only (rank 1), c_overlap_kw (rank 2)
    vec_list = [c_vec_only, c_overlap_vec]
    kw_list = [c_kw_only, c_overlap_kw]

    merged = RetrievalService.reciprocal_rank_fusion([vec_list, kw_list], k=60)

    # c_overlap appears in both lists at rank 2: score = 1/62 + 1/62 = 2/62 ≈ 0.032258
    # c_vec_only appears once at rank 1: score = 1/61 ≈ 0.016393
    # c_kw_only appears once at rank 1: score = 1/61 ≈ 0.016393
    assert len(merged) == 3
    # Overlapping chunk MUST be boosted to #1 because it has matches in both channels
    assert merged[0].chunk_id == cid_overlap
    expected_overlap_score = round((1.0 / 62.0) + (1.0 / 62.0), 6)
    assert merged[0].score == expected_overlap_score


def test_retrieval_filter_to_dict() -> None:
    doc_id = uuid.uuid4()
    rf = RetrievalFilter(
        document_ids=[doc_id],
        page_number=3,
        chunk_types=["table"],
        metadata_filters={"vendor": "Acme"},
    )
    d = rf.to_dict()
    assert d["document_ids"] == [str(doc_id)]
    assert d["page_number"] == 3
    assert d["chunk_types"] == ["table"]
    assert d["metadata"] == {"vendor": "Acme"}


@pytest.mark.asyncio
async def test_search_coordinator_strategies() -> None:
    service = RetrievalService()
    tenant_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    c1 = _create_mock_chunk(uuid.uuid4(), doc_id, "Vec chunk", 0.88, "vector")
    c2 = _create_mock_chunk(uuid.uuid4(), doc_id, "Kw chunk", 0.75, "keyword")

    service.vector_search = AsyncMock(return_value=[c1])
    service.keyword_search = AsyncMock(return_value=[c2])

    mock_session = AsyncMock()

    # 1. Test VECTOR strategy
    results_vec = await service.search(
        session=mock_session,
        tenant_id=tenant_id,
        query="test query",
        strategy=RetrievalStrategy.VECTOR,
        top_k=5,
        log_query=False,
    )
    assert len(results_vec) == 1
    assert results_vec[0].match_type == "vector"
    service.vector_search.assert_awaited_once()

    # 2. Test KEYWORD strategy
    results_kw = await service.search(
        session=mock_session,
        tenant_id=tenant_id,
        query="test query",
        strategy=RetrievalStrategy.KEYWORD,
        top_k=5,
        log_query=False,
    )
    assert len(results_kw) == 1
    assert results_kw[0].match_type == "keyword"
    service.keyword_search.assert_awaited_once()

    # 3. Test HYBRID_RRF strategy
    results_hybrid = await service.search(
        session=mock_session,
        tenant_id=tenant_id,
        query="test query",
        strategy=RetrievalStrategy.HYBRID_RRF,
        top_k=5,
        log_query=False,
    )
    assert len(results_hybrid) == 2
    for item in results_hybrid:
        assert item.match_type == "hybrid"
