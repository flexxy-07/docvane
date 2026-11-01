import logging
import re
import time
from typing import cast

from litellm import completion
from litellm.types.utils import ModelResponse

from backend.app.core.config import settings
from backend.app.services.rag.state import RagState

logger = logging.getLogger(__name__)


class QueryTransformer:
    """
    Transforms user questions using:
    1. Query Rewriting (removes conversational filler, focuses on search keywords).
    2. Multi-Query Expansion (generates 3 diverse query perspectives for RRF).
    3. HyDE (Hypothetical Document Embeddings for conceptual queries).
    """

    def __init__(
        self,
        model_name: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self.model: str = model_name or settings.DEFAULT_LLM_MODEL
        self.api_key: str | None = (
            api_key if api_key is not None else (settings.GEMINI_API_KEY or None)
        )

    def _call_llm(self, prompt: str) -> str:
        if not self.api_key:
            return ""
        try:
            resp = completion(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                api_key=self.api_key,
                temperature=0.2,
                max_tokens=250,
            )
            response = cast(ModelResponse, resp)
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error("LLM call failed in QueryTransformer: %s", str(e))
            return ""

    def rewrite_query(self, question: str) -> str:
        """Transforms a conversational question into a standalone search query."""
        if self.api_key:
            prompt = (
                "You are an expert search query optimizer for business contracts and invoices. "
                "Rewrite the following user question into a concise, keyword-dense search query. "
                "Output ONLY the rewritten search query with no quotes or preamble.\n\n"
                f"Question: {question}"
            )
            llm_res = self._call_llm(prompt).strip().strip('"')
            if llm_res:
                return llm_res

        # Deterministic offline rule-based cleanup
        clean = re.sub(
            r"\b(can\s+you\s+(please\s+)?(tell\s+me|show\s+me|explain)|what\s+(is|are)\s+the|tell\s+me\s+about)\b",
            "",
            question,
            flags=re.IGNORECASE,
        )
        clean = re.sub(r"^(the|a|an)\s+", "", clean.strip(), flags=re.IGNORECASE)
        clean = re.sub(r"[?!.,]", "", clean).strip()

        return clean if len(clean) > 3 else question

    def expand_queries(self, question: str) -> list[str]:
        """Generates 3 diverse formulations of the question for RAG-Fusion."""
        if self.api_key:
            prompt = (
                "Generate 3 distinct search queries related to the following user question "
                "from different angles (lexical, conceptual, and specific clause terms). "
                "Output each query on a new line with no numbering.\n\n"
                f"Question: {question}"
            )
            llm_res = self._call_llm(prompt)
            lines = [
                line.strip().lstrip("123456789.- ")
                for line in llm_res.split("\n")
                if line.strip()
            ]
            if len(lines) >= 2:
                return lines[:3]

        # Deterministic offline variants
        rewritten = self.rewrite_query(question)
        return [
            question,
            rewritten,
            f"{rewritten} clauses and obligations",
        ]

    def generate_hyde(self, question: str) -> str:
        """Generates a hypothetical passage for passage-to-passage search."""
        if self.api_key:
            prompt = (
                "Write a short, realistic 2-sentence passage from a legal contract or "
                "commercial invoice that directly answers this question:\n\n"
                f"Question: {question}\n\nPassage:"
            )
            llm_res = self._call_llm(prompt).strip()
            if llm_res:
                return llm_res

        # Deterministic synthetic fallback
        clean = self.rewrite_query(question)
        return (
            f"Under this agreement, the provisions governing {clean} are set forth "
            "in accordance with standard business terms."
        )


def transform_query_node(state: RagState) -> RagState:
    """
    LangGraph node: Expands and rewrites the query for downstream multi-query retrieval.
    """
    t0 = time.perf_counter()
    transformer = QueryTransformer()
    question = state.get("question", "")
    expanded = transformer.expand_queries(question)
    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 3)

    latencies = state.get("node_latencies", {}).copy()
    latencies["transform_query_node"] = elapsed_ms

    logger.info("Transformed query into %d variants in %.3fms", len(expanded), elapsed_ms)
    return {
        **state,
        "rewritten_queries": expanded,
        "node_latencies": latencies,
    }