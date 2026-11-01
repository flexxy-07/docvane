import enum
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, cast

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.models import DocumentChunk, QueryLog
from backend.app.services.embedding import EmbeddingService

logger = logging.getLogger(__name__)


class RetrievalStrategy(enum.StrEnum):
    VECTOR = "vector"
    KEYWORD = "keyword"
    HYBRID_RRF = "hybrid_rrf"
    HYBRID_RERANK = "hybrid_rerank"


@dataclass
class RetrievedChunk:
    """Represents a scored, retrieved chunk."""

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    page_number: int | None
    chunk_index: int
    chunk_type: str
    content: str
    score: float
    match_type: str  # "vector", "keyword", or "hybrid"
    metadata_json: dict[str, Any] = field(default_factory=dict)


@dataclass
class RetrievalFilter:
    """Filters applied to narrow chunk retrieval."""

    document_ids: list[uuid.UUID] | None = None
    page_number: int | None = None
    chunk_types: list[str] | None = None
    metadata_filters: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        if self.document_ids:
            result["document_ids"] = [str(d) for d in self.document_ids]
        if self.page_number is not None:
            result["page_number"] = self.page_number
        if self.chunk_types:
            result["chunk_types"] = self.chunk_types
        if self.metadata_filters:
            result["metadata"] = self.metadata_filters
        return result


class RetrievalService:
    """
    Multi-stage hybrid retrieval service:
    1. Vector search via pgvector cosine distance (<=>).
    2. Full-text keyword search via PostgreSQL tsvector/ts_rank_cd.
    3. Reciprocal Rank Fusion (RRF) to merge candidate rankings.
    4. Persists search audit trails to query_logs.
    """

    def __init__(self, embedding_service: EmbeddingService | None = None) -> None:
        self.embedding_service = embedding_service or EmbeddingService()

    def _apply_filters(self, stmt: Any, filters: RetrievalFilter | None) -> Any:
        if not filters:
            return stmt

        if filters.document_ids:
            stmt = stmt.where(DocumentChunk.document_id.in_(filters.document_ids))
        if filters.page_number is not None:
            stmt = stmt.where(DocumentChunk.page_number == filters.page_number)
        if filters.chunk_types:
            stmt = stmt.where(DocumentChunk.chunk_type.in_(filters.chunk_types))

        return stmt

    async def vector_search(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        query: str,
        top_k: int = 10,
        filters: RetrievalFilter | None = None,
    ) -> list[RetrievedChunk]:
        """Dense semantic search using pgvector cosine distance."""
        query_vector = self.embedding_service.embed_query(query)
        distance_expr = DocumentChunk.embedding.cosine_distance(query_vector)

        stmt = (
            select(DocumentChunk, distance_expr.label("distance"))
            .where(
                DocumentChunk.tenant_id == tenant_id,
                DocumentChunk.embedding.is_not(None),
            )
        )
        stmt = self._apply_filters(stmt, filters)
        stmt = stmt.order_by(distance_expr.asc()).limit(top_k)

        result = await session.execute(stmt)
        rows = result.all()

        chunks: list[RetrievedChunk] = []
        for row in rows:
            chunk = cast(DocumentChunk, row[0])
            raw_dist = row[1]
            distance = float(raw_dist) if isinstance(raw_dist, (int, float)) else 0.0
            # Cosine similarity score normalized between [0, 1]
            similarity = max(0.0, 1.0 - distance)
            chunks.append(
                RetrievedChunk(
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    page_number=chunk.page_number,
                    chunk_index=chunk.chunk_index,
                    chunk_type=chunk.chunk_type,
                    content=chunk.content,
                    score=round(similarity, 4),
                    match_type="vector",
                    metadata_json=chunk.metadata_json or {},
                )
            )

        return chunks

    async def keyword_search(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        query: str,
        top_k: int = 10,
        filters: RetrievalFilter | None = None,
    ) -> list[RetrievedChunk]:
        """Lexical full-text search using PostgreSQL tsvector and ts_rank_cd."""
        clean_query = query.strip()
        if not clean_query:
            return []

        ts_query = func.plainto_tsquery("english", clean_query)
        ts_vector = func.to_tsvector("english", DocumentChunk.content)
        rank_expr = func.ts_rank_cd(ts_vector, ts_query)

        stmt = (
            select(DocumentChunk, rank_expr.label("rank"))
            .where(
                DocumentChunk.tenant_id == tenant_id,
                ts_vector.op("@@")(ts_query),
            )
        )
        stmt = self._apply_filters(stmt, filters)
        stmt = stmt.order_by(rank_expr.desc()).limit(top_k)

        result = await session.execute(stmt)
        rows = result.all()

        chunks: list[RetrievedChunk] = []
        for row in rows:
            chunk = cast(DocumentChunk, row[0])
            raw_rank = row[1]
            rank = float(raw_rank) if isinstance(raw_rank, (int, float)) else 0.0
            chunks.append(
                RetrievedChunk(
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    page_number=chunk.page_number,
                    chunk_index=chunk.chunk_index,
                    chunk_type=chunk.chunk_type,
                    content=chunk.content,
                    score=round(rank, 4),
                    match_type="keyword",
                    metadata_json=chunk.metadata_json or {},
                )
            )

        return chunks

    @staticmethod
    def reciprocal_rank_fusion(
        ranked_lists: list[list[RetrievedChunk]],
        k: int = 60,
    ) -> list[RetrievedChunk]:
        """
        Combines multiple candidate rankings using Reciprocal Rank Fusion:
        RRF(d) = sum(1 / (k + rank_i(d)))
        """
        rrf_scores: dict[uuid.UUID, float] = {}
        chunk_map: dict[uuid.UUID, RetrievedChunk] = {}

        for r_list in ranked_lists:
            for rank_idx, chunk in enumerate(r_list):
                cid = chunk.chunk_id
                if cid not in chunk_map:
                    chunk_map[cid] = chunk
                # 1-based rank position
                rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (1.0 / (k + rank_idx + 1))

        # Sort by merged RRF score descending
        sorted_chunks = sorted(
            rrf_scores.items(), key=lambda item: item[1], reverse=True
        )

        merged: list[RetrievedChunk] = []
        for cid, score in sorted_chunks:
            original = chunk_map[cid]
            merged.append(
                RetrievedChunk(
                    chunk_id=original.chunk_id,
                    document_id=original.document_id,
                    page_number=original.page_number,
                    chunk_index=original.chunk_index,
                    chunk_type=original.chunk_type,
                    content=original.content,
                    score=round(score, 6),
                    match_type="hybrid",
                    metadata_json=original.metadata_json,
                )
            )

        return merged

    async def search(
        self,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        query: str,
        strategy: RetrievalStrategy = RetrievalStrategy.HYBRID_RRF,
        top_k: int = 5,
        filters: RetrievalFilter | None = None,
        log_query: bool = True,
    ) -> list[RetrievedChunk]:
        """
        Unified search dispatcher supporting vector-only, keyword-only, and hybrid RRF.
        Logs latency and retrieved IDs to query_logs.
        """
        start_time = time.perf_counter()
        results: list[RetrievedChunk] = []

        if strategy == RetrievalStrategy.VECTOR:
            results = await self.vector_search(
                session, tenant_id, query, top_k=top_k, filters=filters
            )
        elif strategy == RetrievalStrategy.KEYWORD:
            results = await self.keyword_search(
                session, tenant_id, query, top_k=top_k, filters=filters
            )
        elif strategy in (RetrievalStrategy.HYBRID_RRF, RetrievalStrategy.HYBRID_RERANK):
            fetch_limit = max(top_k * 2, 10)
            vec_candidates = await self.vector_search(
                session, tenant_id, query, top_k=fetch_limit, filters=filters
            )
            kw_candidates = await self.keyword_search(
                session, tenant_id, query, top_k=fetch_limit, filters=filters
            )
            merged = self.reciprocal_rank_fusion([vec_candidates, kw_candidates], k=60)
            results = merged[:top_k]

        latency_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

        if log_query:
            try:
                top_score = results[0].score if results else None
                query_log = QueryLog(
                    tenant_id=tenant_id,
                    question=query,
                    strategy=strategy.value,
                    route="rag",
                    filters=filters.to_dict() if filters else None,
                    retrieved_chunk_ids=[str(r.chunk_id) for r in results],
                    top_score=top_score,
                    latency_ms=latency_ms,
                    token_count=len(query.split()),
                )
                session.add(query_log)
                await session.commit()
            except Exception as log_err:
                logger.warning("Failed to record query_log: %s", str(log_err))

        return results
