import uuid
from unittest.mock import AsyncMock, MagicMock

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

    # 4. Test HYBRID_RERANK strategy
    mock_reranked = [_create_mock_chunk(uuid.uuid4(), doc_id, "Reranked chunk", 0.95, "reranked")]
    service.reranker.rerank = MagicMock(return_value=mock_reranked)

    results_rerank = await service.search(
        session=mock_session,
        tenant_id=tenant_id,
        query="test query",
        strategy=RetrievalStrategy.HYBRID_RERANK,
        top_k=5,
        log_query=False,
    )
    assert len(results_rerank) == 1
    assert results_rerank[0].match_type == "reranked"
    service.reranker.rerank.assert_called_once()


def test_query_filter_extractor_invoice() -> None:
    from backend.app.services.filter_extraction import QueryFilterExtractor

    extractor = QueryFilterExtractor()
    query = "Show me the line items breakdown in the Acme Corp invoice from 2024 on page 2"
    result = extractor.extract(query)

    assert result.doc_type == "invoice"
    assert result.vendor_name == "Acme Corp"
    assert result.year == 2024
    assert result.page_number == 2
    assert result.filters.chunk_types == ["table"]
    assert result.filters.page_number == 2
    assert result.filters.metadata_filters == {
        "doc_type": "invoice",
        "year": 2024,
        "vendor_name": "Acme Corp",
    }
    assert "invoice" not in result.cleaned_query.lower()
    assert "2024" not in result.cleaned_query


def test_query_filter_extractor_contract() -> None:
    from backend.app.services.filter_extraction import QueryFilterExtractor

    extractor = QueryFilterExtractor()
    query = "What are the termination terms in the NDA agreement with Globex?"
    result = extractor.extract(query)

    assert result.doc_type == "contract"
    assert result.vendor_name == "Globex"
    assert result.filters.metadata_filters == {
        "doc_type": "contract",
        "vendor_name": "Globex",
    }


def test_reranker_service_real_model() -> None:
    from backend.app.services.reranker import RerankerService

    doc_id = uuid.uuid4()
    # Candidate 1: completely irrelevant distractor
    c1 = _create_mock_chunk(
        uuid.uuid4(), doc_id, "The weather is sunny in California.", 0.8, "hybrid"
    )
    # Candidate 2: highly relevant text answering query
    c2 = _create_mock_chunk(
        uuid.uuid4(),
        doc_id,
        "Payment terms are net 30 days after invoice issuance.",
        0.5,
        "hybrid",
    )

    # Test with the REAL BAAI/bge-reranker-base neural cross-encoder
    reranker = RerankerService(enable_model=True)

    reranked = reranker.rerank(
        query="payment terms net 30",
        candidates=[c1, c2],
        top_k=2,
    )

    assert len(reranked) == 2
    # The neural model must rank candidate 2 at #1
    assert reranked[0].chunk_id == c2.chunk_id
    assert reranked[0].match_type == "reranked"
    assert reranked[0].score > reranked[1].score
    # High confidence for relevant text (> 0.80), near zero for irrelevant distractor (< 0.05)
    assert reranked[0].score > 0.80
    assert reranked[1].score < 0.05
