import hashlib
import logging
import math
from pathlib import Path
from typing import Any, cast

import litellm

from backend.app.core.config import settings

logger = logging.getLogger(__name__)

# Cache models on the project drive instead of C: temp
LOCAL_CACHE_DIR = str(Path(__file__).resolve().parents[3] / ".cache" / "fastembed")


def _generate_deterministic_pseudo_vector(text: str, dim: int = 768) -> list[float]:
    """Generates a normalized deterministic pseudo-embedding vector for offline/testing mode."""
    raw_hash = hashlib.sha256(text.encode("utf-8")).digest()
    values: list[float] = []
    for i in range(dim):
        byte_val = raw_hash[i % len(raw_hash)]
        val = (byte_val / 127.5) - 1.0 + (math.sin(i + 1) * 0.1)
        values.append(val)

    norm = math.sqrt(sum(v * v for v in values)) or 1.0
    return [v / norm for v in values]


class EmbeddingService:
    """
    Tiered Embedding Service:
    1. Primary: Cloud Gemini (text-embedding-004, 768-d) via LiteLLM when API key is present.
    2. Fallback: Local FastEmbed ONNX model (BAAI/bge-base-en-v1.5, 768-d) on CPU with 0 API key.
    3. Test mode / safety net: Deterministic unit vector.
    """

    def __init__(
        self,
        model: str | None = None,
        dimensions: int | None = None,
        api_key: str | None = None,
        batch_size: int = 32,
    ) -> None:
        self.model = model or settings.EMBEDDING_MODEL
        self.dimensions = dimensions or settings.EMBEDDING_DIM
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.batch_size = batch_size
        self._local_model: Any = None

    def _get_local_model(self) -> Any:
        """Lazy-loads the local 768-d FastEmbed model."""
        if self._local_model is None:
            try:
                from fastembed import TextEmbedding

                self._local_model = TextEmbedding(
                    model_name="BAAI/bge-base-en-v1.5",
                    cache_dir=LOCAL_CACHE_DIR,
                )
            except Exception as exc:
                logger.warning("Could not initialize local FastEmbed model: %s", str(exc))
                return None
        return self._local_model

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """
        Embeds a list of texts into dense vectors in batches.
        Attempts Cloud Gemini first; gracefully falls back to local FastEmbed, then pseudo-vectors.
        """
        if not texts:
            return []

        embeddings: list[list[float]] = []

        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]

            # Fast path for automated CI tests
            if settings.ENVIRONMENT == "test":
                for text in batch:
                    embeddings.append(_generate_deterministic_pseudo_vector(text, self.dimensions))
                continue

            # 1. Try Cloud Gemini API if API key is configured
            if self.api_key:
                try:
                    response = litellm.embedding(
                        model=self.model,
                        input=batch,
                        api_key=self.api_key,
                    )
                    raw_data = getattr(response, "data", None) or response.get("data", [])  # type: ignore[no-untyped-call]
                    data = cast(list[dict[str, object]], raw_data)
                    for item in data:
                        vec = cast(list[float], item["embedding"])
                        embeddings.append(vec)
                    continue
                except Exception as exc:
                    logger.warning(
                        "Cloud embedding call failed (%s), falling back to local FastEmbed.",
                        str(exc),
                    )

            # 2. Try Local FastEmbed neural model (768 dimensions)
            local_model = self._get_local_model()
            if local_model is not None:
                try:
                    vectors = list(local_model.embed(batch))
                    for v in vectors:
                        vec_list = v.tolist() if hasattr(v, "tolist") else list(v)
                        embeddings.append(cast(list[float], vec_list))
                    continue
                except Exception as exc:
                    logger.warning(
                        "Local FastEmbed call failed (%s), using pseudo-vector fallback.",
                        str(exc),
                    )

            # 3. Deterministic pseudo-vector safety net
            for text in batch:
                embeddings.append(_generate_deterministic_pseudo_vector(text, self.dimensions))

        return embeddings

    def embed_query(self, query: str) -> list[float]:
        """Embeds a single search query string."""
        results = self.embed_texts([query])
        if results:
            return results[0]
        return _generate_deterministic_pseudo_vector(query, self.dimensions)
