import json
import time
import uuid

from fastapi import APIRouter, Depends, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.deps import (
    get_current_tenant_id,
    get_filter_extractor,
    get_retrieval_service,
    get_tenant_db,
)
from backend.app.schemas.retrieval import (
    ChatRequest,
    ChatResponse,
    CitationResponse,
    RetrievedChunkResponse,
    SearchRequest,
    SearchResponse,
)
from backend.app.services.filter_extraction import QueryFilterExtractor
from backend.app.services.rag.graph import execute_rag_pipeline
from backend.app.services.retrieval import RetrievalFilter, RetrievalService

router = APIRouter(prefix="/retrieval", tags=["retrieval"])


@router.post(
    "/search",
    response_model=SearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Hybrid document chunk retrieval",
    description=(
        "Multi-stage retrieval supporting vector search, keyword search, "
        "Reciprocal Rank Fusion (RRF), and cross-encoder reranking."
    ),
)
async def search_documents(
    payload: SearchRequest,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_tenant_db),
    retrieval_service: RetrievalService = Depends(get_retrieval_service),
    filter_extractor: QueryFilterExtractor = Depends(get_filter_extractor),
) -> SearchResponse:
    start_time = time.perf_counter()

    search_query = payload.query
    extracted_filters_dict = None

    # 1. Run natural language filter extraction if enabled
    if payload.enable_filter_extraction:
        extracted = filter_extractor.extract(payload.query)
        search_query = extracted.cleaned_query
        extracted_filters_dict = extracted.extracted_metadata

        # Merge extracted cues with manual overrides
        page_no = (
            payload.page_number
            if payload.page_number is not None
            else extracted.filters.page_number
        )
        c_types = payload.chunk_types or extracted.filters.chunk_types
        doc_ids = payload.document_ids or extracted.filters.document_ids

        active_filter = RetrievalFilter(
            document_ids=doc_ids,
            page_number=page_no,
            chunk_types=c_types,
            metadata_filters=extracted.filters.metadata_filters,
        )
    else:
        active_filter = RetrievalFilter(
            document_ids=payload.document_ids,
            page_number=payload.page_number,
            chunk_types=payload.chunk_types,
        )

    # 2. Execute retrieval via the coordinator service
    chunks = await retrieval_service.search(
        session=session,
        tenant_id=tenant_id,
        query=search_query,
        strategy=payload.strategy,
        top_k=payload.top_k,
        filters=active_filter,
    )

    elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

    return SearchResponse(
        query=payload.query,
        cleaned_query=search_query,
        strategy=payload.strategy.value,
        extracted_filters=extracted_filters_dict,
        latency_ms=elapsed_ms,
        total_results=len(chunks),
        results=[
            RetrievedChunkResponse(
                chunk_id=c.chunk_id,
                document_id=c.document_id,
                page_number=c.page_number,
                chunk_index=c.chunk_index,
                chunk_type=c.chunk_type,
                content=c.content,
                score=c.score,
                match_type=c.match_type,
                metadata=c.metadata_json,
            )
            for c in chunks
        ],
    )


@router.post(
    "/chat",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Self-Correcting RAG & Text-to-SQL Chat endpoint",
    description=(
        "Executes the full LangGraph stateful orchestration pipeline over documents "
        "and structured database tables with adaptive routing, CRAG grading, "
        "Self-RAG answer verification, and citations."
    ),
)
async def chat_with_documents(
    payload: ChatRequest,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_tenant_db),
    retrieval_service: RetrievalService = Depends(get_retrieval_service),
) -> ChatResponse:
    state = await execute_rag_pipeline(
        question=payload.question,
        tenant_id=str(tenant_id),
        session=session,
        retrieval_service=retrieval_service,
        top_k=payload.top_k,
        max_retries=payload.max_retries,
    )

    citations = [
        CitationResponse(
            chunk_id=str(c.get("chunk_id")) if c.get("chunk_id") else None,
            document_id=str(c.get("document_id")) if c.get("document_id") else None,
            page_number=c.get("page_number"),
            score=c.get("score"),
            match_type=c.get("match_type"),
            content=c.get("content"),
        )
        for c in state.get("citations", [])
    ]

    return ChatResponse(
        question=state.get("question", payload.question),
        answer=state.get("answer") or "I could not generate an answer for your inquiry.",
        route=state.get("route", "simple"),
        citations=citations,
        sql_query=state.get("sql_query"),
        rewritten_queries=state.get("rewritten_queries", []),
        retry_count=state.get("retry_count", 0),
        node_latencies=state.get("node_latencies", {}),
    )


@router.post(
    "/chat/stream",
    summary="Real-time token streaming RAG Chat endpoint",
    description="Streams tokens directly from the LLM as they are generated using Server-Sent Events (SSE).",
)
async def chat_stream_with_documents(
    payload: ChatRequest,
    tenant_id: uuid.UUID = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_tenant_db),
    retrieval_service: RetrievalService = Depends(get_retrieval_service),
):
    from backend.app.services.rag.nodes.generation import AnswerGenerator
    from backend.app.services.rag.nodes.retrieval import retrieve_node

    async def event_generator():
        try:
            # 1. Multi-stage hybrid retrieval
            retrieval_state = await retrieve_node(
                {"question": payload.question, "tenant_id": str(tenant_id)},
                config={
                    "configurable": {
                        "session": session,
                        "retrieval_service": retrieval_service,
                        "top_k": payload.top_k,
                    }
                },
            )
            chunks = retrieval_state.get("retrieved_chunks", [])

            # Yield citations immediately so the client can prepare source metadata
            citations = [
                {
                    "chunk_id": str(c.get("chunk_id")) if c.get("chunk_id") else None,
                    "document_id": str(c.get("document_id")) if c.get("document_id") else None,
                    "page_number": c.get("page_number"),
                    "score": c.get("score"),
                    "match_type": c.get("match_type"),
                    "content": c.get("content"),
                }
                for c in chunks[:5]
            ]
            yield f"data: {json.dumps({'type': 'sources', 'citations': citations})}\n\n"

            # 2. Stream tokens from the LLM as each token is generated
            generator = AnswerGenerator()
            for token in generator.stream_answer(payload.question, chunks):
                yield f"data: {json.dumps({'type': 'token', 'token': token})}\n\n"

            # 3. Completion signal
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


