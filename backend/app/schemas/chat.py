import uuid
from typing import Any

from pydantic import BaseModel, Field


class CitationItem(BaseModel):
    chunk_id: str | None = None
    document_id: str | uuid.UUID | None = None
    page_number: int | None = None
    score: float | None = None
    match_type: str | None = None


class ChatRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="User question or query about contracts, invoices, or business terms.",
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of relevant document chunks to retrieve.",
    )


class ChatResponse(BaseModel):
    question: str
    answer: str
    route: str = Field(
        ...,
        description="Route taken by LangGraph: direct | simple | transform | sql | both",
    )
    sql_query: str | None = None
    citations: list[CitationItem] = Field(default_factory=list)
    grade: str | None = None
    retry_count: int = 0
    node_latencies: dict[str, float] = Field(default_factory=dict)
    total_latency_ms: float = 0.0
