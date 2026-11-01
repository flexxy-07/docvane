import logging
import math
import re
from pathlib import Path
from typing import Any

from backend.app.core.config import settings
from backend.app.services.retrieval import RetrievedChunk

logger = logging.getLogger(__name__)

LOCAL_CACHE_DIR = str(Path(__file__).resolve().parents[3] / ".cache" / "fastembed")


def _heuristic_cross_score(query: str, content: str, initial_score: float) -> float:
    """
    Fast offline cross-encoder scoring simulator:
    Combines exact query term coverage with initial candidate rank.
    Produces calibrated relevance score in [0.0, 1.0].
    """
    q_words = set(re.findall(r"\w+", query.lower()))
    if not q_words:
        return initial_score

    c_words = set(re.findall(r"\w+", content.lower()))
    matches = q_words.intersection(c_words)
    coverage = len(matches) / len(q_words)

    # Sigmoid-like blend: 60% term coverage + 40% initial vector/hybrid score
    raw_val = (coverage * 0.6) + (min(1.0, initial_score) * 0.4)
    return round(raw_val, 4)


class RerankerService:
    """
    Cross-Encoder Reranker:
    Passes (query, passage) pairs together through cross-attention transformer layers.
    Primary: FastEmbed TextCrossEncoder (BAAI/bge-reranker-base).
    Fallback: Heuristic term-coverage cross-scorer for offline/testing mode.
    """

    def __init__(
        self,
        model_name: str | None = None,
        cache_dir: str | None = None,
        enable_model: bool = True,
    ) -> None:
        self.model_name = model_name or settings.RERANKER_MODEL
        self.cache_dir = cache_dir or LOCAL_CACHE_DIR
        self.enable_model = enable_model
        self._model: Any = None

    def _get_model(self) -> Any:
        """Lazy-loads the local cross-encoder model."""
        if not self.enable_model:
            return None

        if self._model is None:
            try:
                from fastembed.rerank.cross_encoder import TextCrossEncoder

                self._model = TextCrossEncoder(
                    model_name=self.model_name,
                    cache_dir=self.cache_dir,
                )
            except Exception as exc:
                logger.warning(
                    "FastEmbed TextCrossEncoder unavailable (%s); using fallback cross-scorer.",
                    str(exc),
                )
        return self._model

    def rerank(
        self,
        query: str,
        candidates: list[RetrievedChunk],
        top_k: int = 5,
    ) -> list[RetrievedChunk]:
        """
        Reranks a list of candidate chunks against the query and returns top_k.
        """
        if not candidates:
            return []

        model = self._get_model()
        scored_candidates: list[tuple[float, RetrievedChunk]] = []

        if model is not None:
            try:
                docs = [c.content for c in candidates]
                scores = list(model.rerank(query, docs))
                for score, candidate in zip(scores, candidates, strict=True):
                    # Sigmoid normalize if needed or clamp [0, 1]
                    s_float = float(score)
                    # Standard sigmoid mapping cross-encoder logits into [0.0, 1.0] range
                    norm_score = 1.0 / (1.0 + math.exp(-s_float))
                    norm_score = min(1.0, max(0.0, norm_score))
                    scored_candidates.append((norm_score, candidate))
            except Exception as exc:
                logger.warning(
                    "Reranker execution error (%s); falling back to heuristic.",
                    str(exc),
                )
                scored_candidates = [
                    (_heuristic_cross_score(query, c.content, c.score), c)
                    for c in candidates
                ]
        else:
            scored_candidates = [
                (_heuristic_cross_score(query, c.content, c.score), c)
                for c in candidates
            ]

        # Sort descending by rerank score
        scored_candidates.sort(key=lambda x: x[0], reverse=True)

        reranked: list[RetrievedChunk] = []
        for score, cand in scored_candidates[:top_k]:
            reranked.append(
                RetrievedChunk(
                    chunk_id=cand.chunk_id,
                    document_id=cand.document_id,
                    page_number=cand.page_number,
                    chunk_index=cand.chunk_index,
                    chunk_type=cand.chunk_type,
                    content=cand.content,
                    score=round(score, 4),
                    match_type="reranked",
                    metadata_json=cand.metadata_json,
                )
            )

        return reranked
