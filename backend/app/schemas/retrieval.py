import uuid
from typing import Any

from pydantic import BaseModel, Field

from backend.app.services.retrieval import RetrievalStrategy


class SearchRequest(BaseModel):
    """Payload for executing hybrid document retrieval."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Natural language question or search query",
        examples=["What is the total due amount in the Acme invoice from 2024?"],
    )
    strategy: RetrievalStrategy = Field(
        default=RetrievalStrategy.HYBRID_RRF,
        description="Retrieval strategy: vector, keyword, hybrid_rrf, or hybrid_rerank",
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Number of highest-ranking chunks to return",
    )
    document_ids: list[uuid.UUID] | None = Field(
        default=None,
        description="Optional list of document UUIDs to scope retrieval to",
    )
    page_number: int | None = Field(
        default=None,
        ge=1,
        description="Optional page number filter",
    )
    chunk_types: list[str] | None = Field(
        default=None,
        description="Optional chunk types filter (e.g. ['table', 'text'])",
    )
    enable_filter_extraction: bool = Field(
        default=True,
        description="Auto-extract vendor, year, and table cues from the query text",
    )


class RetrievedChunkResponse(BaseModel):
    """Details of an individual retrieved chunk with scoring metadata."""

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    page_number: int | None
    chunk_index: int
    chunk_type: str
    content: str
    score: float
    match_type: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchResponse(BaseModel):
    """Complete retrieval search response."""

    query: str
    cleaned_query: str
    strategy: str
    extracted_filters: dict[str, Any] | None = None
    latency_ms: float
    total_results: int
    results: list[RetrievedChunkResponse]


class CitationResponse(BaseModel):
    """Citation referencing a specific document, page, and chunk excerpt."""

    chunk_id: str | None = None
    document_id: str | None = None
    page_number: int | None = None
    score: float | None = None
    match_type: str | None = None
    content: str | None = None


class ChatRequest(BaseModel):
    """Payload for asking questions to the Self-Correcting RAG & Text-to-SQL pipeline."""

    question: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Natural language question or query",
        examples=["What is the total amount due across all Acme invoices?"],
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Number of highest-ranking chunks to retrieve",
    )
    max_retries: int = Field(
        default=2,
        ge=0,
        le=5,
        description="Maximum corrective retry loops for passage grading",
    )


class ChatResponse(BaseModel):
    """Complete response from the Self-Correcting LangGraph RAG pipeline."""

    question: str
    answer: str
    route: str = Field(
        description="Branch selected by query router: direct | simple | transform | sql | both"
    )
    citations: list[CitationResponse] = Field(default_factory=list)
    sql_query: str | None = None
    rewritten_queries: list[str] = Field(default_factory=list)
    retry_count: int = 0
    node_latencies: dict[str, float] = Field(default_factory=dict)

