import uuid
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.api.deps import (
    get_filter_extractor,
    get_retrieval_service,
    get_tenant_db,
)
from backend.app.main import app
from backend.app.services.filter_extraction import ExtractedFilters, QueryFilterExtractor
from backend.app.services.retrieval import (
    RetrievalFilter,
    RetrievalService,
    RetrievedChunk,
)


@pytest.fixture
def tenant_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def doc_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def mock_retrieved_chunk(doc_id: uuid.UUID) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=uuid.uuid4(),
        document_id=doc_id,
        page_number=1,
        chunk_index=0,
        chunk_type="table",
        content="| Item | Total |\n|---|---|\n| Widget A | $100 |",
        score=0.0325,
        match_type="hybrid",
        metadata_json={"vendor": "Acme Corp"},
    )


@pytest.fixture
def mock_retrieval_service(mock_retrieved_chunk: RetrievedChunk) -> MagicMock:
    service = MagicMock(spec=RetrievalService)
    service.search = AsyncMock(return_value=[mock_retrieved_chunk])
    return service


@pytest.fixture
def mock_filter_extractor() -> MagicMock:
    extractor = MagicMock(spec=QueryFilterExtractor)
    extractor.extract.return_value = ExtractedFilters(
        filters=RetrievalFilter(chunk_types=["table"]),
        doc_type="invoice",
        vendor_name="Acme Corp",
        year=2024,
        cleaned_query="line items breakdown",
        extracted_metadata={"doc_type": "invoice", "vendor_name": "Acme Corp", "year": 2024},
    )
    return extractor


@pytest.mark.asyncio
async def test_search_missing_tenant_header() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/retrieval/search",
            json={"query": "payment terms"},
        )
    assert response.status_code == 400
    assert "Missing required header 'X-Tenant-ID'" in response.json()["detail"]


@pytest.mark.asyncio
async def test_search_invalid_tenant_uuid() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/retrieval/search",
            headers={"X-Tenant-ID": "invalid-uuid"},
            json={"query": "payment terms"},
        )
    assert response.status_code == 400
    assert "must be a valid UUID format" in response.json()["detail"]


@pytest.mark.asyncio
async def test_search_endpoint_success_hybrid(
    tenant_id: uuid.UUID,
    mock_retrieval_service: MagicMock,
    mock_filter_extractor: MagicMock,
    mock_retrieved_chunk: RetrievedChunk,
) -> None:
    async def override_get_tenant_db() -> AsyncGenerator[AsyncMock, None]:
        yield AsyncMock()

    app.dependency_overrides[get_tenant_db] = override_get_tenant_db
    app.dependency_overrides[get_retrieval_service] = lambda: mock_retrieval_service
    app.dependency_overrides[get_filter_extractor] = lambda: mock_filter_extractor

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/retrieval/search",
                headers={"X-Tenant-ID": str(tenant_id)},
                json={
                    "query": "Show me the line items in the Acme invoice from 2024",
                    "strategy": "hybrid_rrf",
                    "top_k": 3,
                    "enable_filter_extraction": True,
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["query"] == "Show me the line items in the Acme invoice from 2024"
        assert data["cleaned_query"] == "line items breakdown"
        assert data["strategy"] == "hybrid_rrf"
        assert data["extracted_filters"]["vendor_name"] == "Acme Corp"
        assert data["total_results"] == 1
        assert len(data["results"]) == 1
        assert data["results"][0]["chunk_id"] == str(mock_retrieved_chunk.chunk_id)
        assert data["results"][0]["match_type"] == "hybrid"
        assert data["latency_ms"] >= 0.0

        mock_retrieval_service.search.assert_awaited_once()
        mock_filter_extractor.extract.assert_called_once()
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_search_endpoint_rerank_strategy(
    tenant_id: uuid.UUID,
    mock_retrieval_service: MagicMock,
    mock_filter_extractor: MagicMock,
    mock_retrieved_chunk: RetrievedChunk,
) -> None:
    mock_retrieved_chunk.match_type = "reranked"
    mock_retrieved_chunk.score = 0.96

    async def override_get_tenant_db() -> AsyncGenerator[AsyncMock, None]:
        yield AsyncMock()

    app.dependency_overrides[get_tenant_db] = override_get_tenant_db
    app.dependency_overrides[get_retrieval_service] = lambda: mock_retrieval_service
    app.dependency_overrides[get_filter_extractor] = lambda: mock_filter_extractor

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/retrieval/search",
                headers={"X-Tenant-ID": str(tenant_id)},
                json={
                    "query": "payment terms net 30",
                    "strategy": "hybrid_rerank",
                    "top_k": 5,
                    "enable_filter_extraction": False,
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["strategy"] == "hybrid_rerank"
        assert data["cleaned_query"] == "payment terms net 30"
        assert data["results"][0]["match_type"] == "reranked"
        assert data["results"][0]["score"] == 0.96
        # Filter extraction was disabled, so extracted_filters is None
        assert data["extracted_filters"] is None
        mock_filter_extractor.extract.assert_not_called()
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_chat_missing_tenant_header() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/retrieval/chat",
            json={"question": "What is the termination clause?"},
        )
    assert response.status_code == 400
    assert "Missing required header 'X-Tenant-ID'" in response.json()["detail"]


@pytest.mark.asyncio
async def test_chat_invalid_tenant_uuid() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/retrieval/chat",
            headers={"X-Tenant-ID": "bad-uuid"},
            json={"question": "What is the termination clause?"},
        )
    assert response.status_code == 400
    assert "must be a valid UUID format" in response.json()["detail"]


@pytest.mark.asyncio
async def test_chat_endpoint_success_direct(
    tenant_id: uuid.UUID,
    mock_retrieval_service: MagicMock,
) -> None:
    async def override_get_tenant_db() -> AsyncGenerator[AsyncMock, None]:
        yield AsyncMock()

    app.dependency_overrides[get_tenant_db] = override_get_tenant_db
    app.dependency_overrides[get_retrieval_service] = lambda: mock_retrieval_service

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/retrieval/chat",
                headers={"X-Tenant-ID": str(tenant_id)},
                json={"question": "Hello, how can you help me?"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["question"] == "Hello, how can you help me?"
        assert data["route"] == "direct"
        assert "Docvane" in data["answer"]
        assert data["citations"] == []
        assert data["sql_query"] is None
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_chat_endpoint_success_with_citations_and_sql(
    tenant_id: uuid.UUID,
    mock_retrieval_service: MagicMock,
) -> None:
    async def override_get_tenant_db() -> AsyncGenerator[AsyncMock, None]:
        yield AsyncMock()

    mock_state = {
        "question": "What are the total charges for Acme Corp in 2024?",
        "tenant_id": str(tenant_id),
        "route": "both",
        "answer": "Acme Corp charges totaled $15,400.00 across 3 invoices.",
        "citations": [
            {
                "chunk_id": "c1111111-1111-1111-1111-111111111111",
                "document_id": "d2222222-2222-2222-2222-222222222222",
                "page_number": 2,
                "score": 0.88,
                "match_type": "hybrid",
                "content": "Invoice Total: $15,400.00",
            }
        ],
        "sql_query": "SELECT SUM(total_amount) FROM invoices WHERE vendor_name = 'Acme Corp'",
        "rewritten_queries": ["Acme Corp 2024 invoice total", "Acme Corporation annual spend"],
        "retry_count": 0,
        "node_latencies": {"router": 5.2, "sql_node": 12.1, "generate_node": 25.4},
    }

    app.dependency_overrides[get_tenant_db] = override_get_tenant_db
    app.dependency_overrides[get_retrieval_service] = lambda: mock_retrieval_service

    with patch(
        "backend.app.api.v1.retrieval.execute_rag_pipeline",
        new=AsyncMock(return_value=mock_state),
    ) as mock_exec:
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/retrieval/chat",
                    headers={"X-Tenant-ID": str(tenant_id)},
                    json={
                        "question": "What are the total charges for Acme Corp in 2024?",
                        "top_k": 3,
                        "max_retries": 1,
                    },
                )

            assert response.status_code == 200
            data = response.json()
            assert data["question"] == "What are the total charges for Acme Corp in 2024?"
            assert data["route"] == "both"
            assert data["answer"] == "Acme Corp charges totaled $15,400.00 across 3 invoices."
            assert len(data["citations"]) == 1
            assert data["citations"][0]["chunk_id"] == "c1111111-1111-1111-1111-111111111111"
            assert data["citations"][0]["page_number"] == 2
            assert data["citations"][0]["content"] == "Invoice Total: $15,400.00"
            assert "SELECT SUM" in (data["sql_query"] or "")
            assert len(data["rewritten_queries"]) == 2
            assert data["node_latencies"]["sql_node"] == 12.1

            mock_exec.assert_awaited_once_with(
                question="What are the total charges for Acme Corp in 2024?",
                tenant_id=str(tenant_id),
                session=mock_exec.call_args.kwargs["session"],
                retrieval_service=mock_retrieval_service,
                top_k=3,
                max_retries=1,
            )
        finally:
            app.dependency_overrides.clear()

