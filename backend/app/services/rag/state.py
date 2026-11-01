from typing import Any, TypedDict


class RagState(TypedDict, total=False):
    """
    Central state container for the Docvane LangGraph RAG pipeline.
    Tracks routing decisions, query transformations, retrieved passages,
    grading, generated answers, and citations across all graph nodes.
    """

    question: str
    tenant_id: str
    route: str  # "direct" | "simple" | "transform" | "sql" | "both"
    rewritten_queries: list[str]
    filters: dict[str, Any]
    retrieved_chunks: list[dict[str, Any]]
    grade: str | None  # "relevant" | "irrelevant"
    answer: str | None
    citations: list[dict[str, Any]]
    sql_query: str | None
    retry_count: int
    node_latencies: dict[str, float]
    error: str | None
