import inspect
import logging
import time
import uuid
from typing import Any

from langchain_core.runnables import RunnableConfig

from backend.app.services.filter_extraction import QueryFilterExtractor
from backend.app.services.rag.state import RagState
from backend.app.services.retrieval import (
    RetrievalFilter,
    RetrievalService,
    RetrievalStrategy,
    RetrievedChunk,
)

logger = logging.getLogger(__name__)


async def retrieve_node(
    state: RagState,
    config: RunnableConfig | None = None,
) -> RagState:
    """
    LangGraph node: Multi-stage hybrid retrieval node.
    - Extracts metadata filters from the question (if not present).
    - If multiple rewritten queries exist (from transform_query_node),
      executes RAG-Fusion across all queries via Reciprocal Rank Fusion (RRF).
    - If a single query exists, executes standard hybrid search + reranking.
    - Saves retrieved chunks and latency metrics to state.
    """
    t0 = time.perf_counter()
    conf = config.get("configurable", {}) if config else {}

    session = conf.get("session")
    retrieval_service: RetrievalService | None = conf.get("retrieval_service")
    top_k: int = conf.get("top_k", 5)

    question = state.get("question", "")
    tenant_str = state.get("tenant_id", "")
    try:
        tenant_id = uuid.UUID(tenant_str)
    except (ValueError, TypeError):
        tenant_id = uuid.uuid4()

    # 1. Natural Language Filter Extraction
    filters_dict = state.get("filters")
    active_filter: RetrievalFilter | None = None

    if not filters_dict:
        extractor = QueryFilterExtractor()
        extracted = extractor.extract(question)
        active_filter = extracted.filters
        filters_dict = extracted.extracted_metadata
    else:
        # Convert dictionary filters back to RetrievalFilter
        active_filter = RetrievalFilter(
            document_ids=[
                uuid.UUID(d) for d in filters_dict.get("document_ids", [])
            ] or None,
            page_number=filters_dict.get("page_number"),
            chunk_types=filters_dict.get("chunk_types"),
            metadata_filters=filters_dict.get("metadata"),
        )

    retrieved_chunks: list[dict[str, Any]] = []

    # 2. Execute retrieval if DB session & service are available
    if session and retrieval_service:
        queries = state.get("rewritten_queries") or [question]

        chunks_to_export: list[RetrievedChunk] = []

        if len(queries) > 1:
            # Multi-Query RAG-Fusion: Retrieve top candidates per query perspective
            ranked_runs: list[list[RetrievedChunk]] = []
            for q in queries:
                res = await retrieval_service.search(
                    session=session,
                    tenant_id=tenant_id,
                    query=q,
                    strategy=RetrievalStrategy.HYBRID_RRF,
                    top_k=top_k * 2,
                    filters=active_filter,
                )
                if res:
                    ranked_runs.append(res)

            if ranked_runs:
                fused = RetrievalService.reciprocal_rank_fusion(ranked_runs)
                # Final rerank against the primary original question
                rerank_out = retrieval_service.reranker.rerank(
                    query=question,
                    chunks=fused,
                    top_k=top_k,
                )
                if inspect.isawaitable(rerank_out):
                    chunks_to_export = await rerank_out
                else:
                    chunks_to_export = rerank_out
        else:
            # Single-query direct hybrid search + rerank
            chunks_to_export = await retrieval_service.search(
                session=session,
                tenant_id=tenant_id,
                query=queries[0],
                strategy=RetrievalStrategy.HYBRID_RERANK,
                top_k=top_k,
                filters=active_filter,
            )

        retrieved_chunks = [
            {
                "chunk_id": str(c.chunk_id),
                "document_id": str(c.document_id),
                "page_number": c.page_number,
                "chunk_index": c.chunk_index,
                "chunk_type": c.chunk_type,
                "content": c.content,
                "score": c.score,
                "match_type": c.match_type,
                "metadata": c.metadata_json,
            }
            for c in chunks_to_export
        ]
    else:
        # Offline or mock fallback (e.g. when state already has chunks or during mock tests)
        retrieved_chunks = state.get("retrieved_chunks", [])
        logger.info(
            "retrieve_node executing without active DB session. "
            "Retained %d pre-existing chunks.",
            len(retrieved_chunks),
        )

    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 3)
    latencies = state.get("node_latencies", {}).copy()
    latencies["retrieve_node"] = elapsed_ms

    logger.info(
        "retrieve_node finished in %.3fms with %d chunks",
        elapsed_ms,
        len(retrieved_chunks),
    )

    return {
        **state,
        "filters": filters_dict or {},
        "retrieved_chunks": retrieved_chunks,
        "node_latencies": latencies,
    }
