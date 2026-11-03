from typing import Any, TypedDict


class SqlState(TypedDict, total=False):
    """
    State container for the Text-to-SQL LangGraph agent sub-graph.
    Tracks query generation, security validation, execution results,
    explanation, error retry loops, and node latencies.
    """

    question: str
    tenant_id: str
    sql_query: str | None
    sql_results: list[dict[str, Any]] | None
    validation_error: str | None
    execution_error: str | None
    explanation: str | None
    retry_count: int
    node_latencies: dict[str, float]
