import logging
import re
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
            api_key if api_key is not None else (settings.effective_gemini_api_key or None)
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
                max_tokens=800,
            )
            response = cast(ModelResponse, resp)
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error("LLM call failed in AnswerGenerator: %s", str(e))
            return ""

    def generate(self, question: str, chunks: list[dict[str, Any]]) -> str:
        """Generates a structured, concise answer from context passages."""
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
            # Collapse repeated whitespace
            clean_content = re.sub(r"\n{2,}", "\n", content)
            context_blocks.append(f"[Source {idx} - Doc: {doc_id}, {page_str}]\n{clean_content}")

        context_text = "\n\n".join(context_blocks)

        if self.api_key:
            prompt = (
                "You are Docvane, an intelligent document analysis and RAG assistant.\n"
                "Your objective is to directly, accurately, and concisely answer the user's question "
                "using ONLY the provided context passages below.\n\n"
                "Strict Formatting Rules:\n"
                "1. Answer the question directly and cleanly without unnecessary preamble or repeating raw file headers.\n"
                "2. When listing team members, names, roles, deliverables, dates, financial amounts, or terms, format them as clean, organized Markdown bullet points or numbered lists.\n"
                "3. Cite the source for each claim using brackets, e.g., [Source 1] or [Page 1].\n"
                "4. If the requested information is not mentioned in the context, clearly state that it was not found in the documents.\n\n"
                f"Context Passages:\n{context_text}\n\n"
                f"User Question: {question}\n\n"
                "Direct Structured Answer:"
            )
            llm_res = self._call_llm(prompt).strip()
            if llm_res:
                return llm_res

        # If LLM call could not be completed, synthesize a clean structured extraction instead of dumping raw text
        top_chunk = chunks[0]
        top_page = top_chunk.get("page_number", 1)
        raw = top_chunk.get("content", "")
        lines = [line.strip() for line in raw.split("\n") if line.strip()]
        meaningful = [l for l in lines if not l.startswith("[Document:") and len(l) > 2][:8]
        bullets = "\n".join(f"• {l}" for l in meaningful) if meaningful else raw[:200]
        return (
            f"Based on Page {top_page} of your document [Source 1]:\n\n"
            f"{bullets}"
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
