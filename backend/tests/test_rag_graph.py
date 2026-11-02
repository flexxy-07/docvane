import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.app.services.rag.graph import execute_rag_pipeline
from backend.app.services.retrieval import RetrievedChunk


@pytest.mark.asyncio
async def test_graph_direct_greeting_route() -> None:
    """Verifies direct route shortcuts DB retrieval and answers immediately."""
    result = await execute_rag_pipeline(
        question="Hello, who are you and what can you do?",
        tenant_id=str(uuid.uuid4()),
    )

    assert result["route"] == "direct"
    assert "Docvane" in (result.get("answer") or "")
    assert result.get("citations") == []
    # Verify node execution path
    latencies = result.get("node_latencies", {})
    assert "router_node" in latencies
    assert "direct_answer_node" in latencies
    assert "retrieve_node" not in latencies
    assert "transform_query_node" not in latencies


@pytest.mark.asyncio
async def test_graph_simple_query_route() -> None:
    """Verifies targeted simple queries route straight to retrieval without transform."""
    mock_retrieval = MagicMock()
    mock_chunk = RetrievedChunk(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        page_number=1,
        chunk_index=0,
        chunk_type="text",
        content="Invoice Number: INV-98765 for Acme Corp.",
        score=0.89,
        match_type="hybrid_reranked",
        metadata_json={},
    )
    mock_retrieval.search = AsyncMock(return_value=[mock_chunk])

    result = await execute_rag_pipeline(
        question="What is the invoice number on the Acme PDF?",
        tenant_id=str(uuid.uuid4()),
        session=MagicMock(),
        retrieval_service=mock_retrieval,
    )

    assert result["route"] == "simple"
    latencies = result.get("node_latencies", {})
    assert "router_node" in latencies
    assert "retrieve_node" in latencies
    assert "grade_passages_node" in latencies
    assert "generate_node" in latencies
    assert "check_answer_support_node" in latencies
    assert "transform_query_node" not in latencies


@pytest.mark.asyncio
async def test_graph_transform_multi_query_route() -> None:
    """Verifies complex queries trigger transform_query before retrieval."""
    result = await execute_rag_pipeline(
        question="Compare and contrast the liability clauses between Acme and Globex",
        tenant_id=str(uuid.uuid4()),
    )

    assert result["route"] == "transform"
    assert len(result.get("rewritten_queries", [])) >= 2

    latencies = result.get("node_latencies", {})
    assert "router_node" in latencies
    assert "transform_query_node" in latencies
    assert "retrieve_node" in latencies
    assert "grade_passages_node" in latencies
    assert "generate_node" in latencies
    assert "check_answer_support_node" in latencies


@pytest.mark.asyncio
async def test_graph_retrieval_and_citation_generation() -> None:
    """Verifies end-to-end chunk propagation, answer generation, and citation extraction."""
    mock_retrieval_service = MagicMock()
    mock_chunk = RetrievedChunk(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        page_number=3,
        chunk_index=1,
        chunk_type="text",
        content="Acme Corp agrees to indemnify Globex against third-party claims.",
        score=0.92,
        match_type="hybrid_reranked",
        metadata_json={"vendor": "Acme Corp"},
    )
    mock_retrieval_service.search = AsyncMock(return_value=[mock_chunk])

    result = await execute_rag_pipeline(
        question="What are the indemnification terms with Acme?",
        tenant_id=str(uuid.uuid4()),
        session=MagicMock(),  # indicates active DB session to retrieve_node
        retrieval_service=mock_retrieval_service,
    )

    chunks = result.get("retrieved_chunks", [])
    assert len(chunks) == 1
    assert chunks[0]["page_number"] == 3
    assert "indemnify Globex" in chunks[0]["content"]

    citations = result.get("citations", [])
    assert len(citations) == 1
    assert citations[0]["page_number"] == 3
    assert citations[0]["chunk_id"] == str(mock_chunk.chunk_id)

    answer = result.get("answer") or ""
    assert "Source 1" in answer or "indemnify" in answer.lower()
    assert result.get("grade") == "supported"


@pytest.mark.asyncio
async def test_graph_corrective_retry_loop_on_irrelevant_chunks() -> None:
    """
    CRAG test: When retrieved chunks are irrelevant, the graph loops back to
    transform_query_node, increments retry_count, and terminates when max_retries is reached.
    """
    mock_retrieval_service = MagicMock()
    # Return completely irrelevant chunk so grade_passages marks it 'irrelevant'
    irrelevant_chunk = RetrievedChunk(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        page_number=1,
        chunk_index=0,
        chunk_type="text",
        content="The parking lot is closed for sweeping on Sunday mornings.",
        score=0.01,
        match_type="hybrid",
        metadata_json={},
    )
    mock_retrieval_service.search = AsyncMock(return_value=[irrelevant_chunk])
    mock_retrieval_service.reranker.rerank.return_value = [irrelevant_chunk]

    result = await execute_rag_pipeline(
        question="What are the governing law provisions for dispute resolution?",
        tenant_id=str(uuid.uuid4()),
        session=MagicMock(),
        retrieval_service=mock_retrieval_service,
    )

    # Verify that corrective loop fired and retry limit was respected
    assert result.get("retry_count", 0) >= 2
    latencies = result.get("node_latencies", {})
    assert "grade_passages_node" in latencies
    assert "generate_node" in latencies
    assert "check_answer_support_node" in latencies

