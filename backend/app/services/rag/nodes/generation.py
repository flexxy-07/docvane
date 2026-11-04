import logging
import time
from typing import Any, cast

from litellm import completion
from litellm.types.utils import ModelResponse

from backend.app.core.config import settings
from backend.app.services.rag.state import RagState

logger = logging.getLogger(__name__)


class AnswerGenerator:
    """
    Synthesizes answers grounded in retrieved document chunks with page citations.
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
                temperature=0.1,
                max_tokens=600,
            )
            response = cast(ModelResponse, resp)
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error("LLM call failed in AnswerGenerator: %s", str(e))
            return ""

    def generate(self, question: str, chunks: list[dict[str, Any]]) -> str:
        """Generates an answer from context passages or falls back to extraction."""
        if not chunks:
            return (
                "I could not find relevant passages in your uploaded documents "
                "to answer this question. Please ensure your documents are uploaded and indexed."
            )

        context_blocks: list[str] = []
        for idx, c in enumerate(chunks[:5], start=1):
            doc_id = c.get("document_id", "unknown")
            page = c.get("page_number")
            page_str = f"Page {page}" if page is not None else "Page N/A"
            content = c.get("content", "").strip()
            context_blocks.append(f"[Source {idx} - Doc: {doc_id}, {page_str}]\n{content}")

        context_text = "\n\n".join(context_blocks)

        if self.api_key:
            prompt = (
                "You are Docvane, an expert legal contract and commercial invoice analyst. "
                "Answer the user's question based strictly on the provided context passages below. "
                "For every claim made in your answer, cite the corresponding source in brackets "
                "like [Source 1] or [Page X]. "
                "If the context does not contain the answer, state that the information "
                "is missing.\n\n"
                f"Context:\n{context_text}\n\n"
                f"Question: {question}\n\n"
                "Answer:"
            )
            llm_res = self._call_llm(prompt).strip()
            if llm_res:
                return llm_res

        # Deterministic offline fallback: Summarize top chunk content with citation
        top_chunk = chunks[0]
        top_page = top_chunk.get("page_number")
        page_ref = f" (Page {top_page})" if top_page is not None else ""
        return (
            f"Based on the retrieved document records{page_ref}:\n\n"
            f'"{top_chunk.get("content", "").strip()}"\n\n'
            f"[Source 1 - Doc: {top_chunk.get('document_id', 'unknown')}]"
        )


def generate_node(state: RagState) -> RagState:
    """
    LangGraph node: Formats retrieved context, calls LLM to synthesize an answer,
    extracts citations, and records latency.
    """
    t0 = time.perf_counter()
    generator = AnswerGenerator()
    question = state.get("question", "")
    chunks = state.get("retrieved_chunks", [])

    doc_answer = generator.generate(question, chunks)
    sql_answer = state.get("answer")
    if sql_answer:
        final_answer = f"{sql_answer}\n\n### Document Analysis:\n{doc_answer}"
    else:
        final_answer = doc_answer

    citations: list[dict[str, Any]] = [
        {
            "chunk_id": c.get("chunk_id"),
            "document_id": c.get("document_id"),
            "page_number": c.get("page_number"),
            "score": c.get("score"),
            "match_type": c.get("match_type"),
            "content": c.get("content"),
        }
        for c in chunks[:5]
    ]

    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 3)
    latencies = state.get("node_latencies", {}).copy()
    latencies["generate_node"] = elapsed_ms

    logger.info("generate_node completed in %.3fms with %d citations", elapsed_ms, len(citations))

    return {
        **state,
        "answer": final_answer,
        "citations": citations,
        "node_latencies": latencies,
    }
