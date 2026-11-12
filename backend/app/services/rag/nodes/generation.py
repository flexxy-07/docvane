import logging
import re
import time
from typing import Any, cast

from litellm import completion
from litellm.types.utils import ModelResponse

from backend.app.core.config import settings
from backend.app.services.rag.state import RagState

logger = logging.getLogger(__name__)

STOP_WORDS = {
    "the", "a", "an", "and", "or", "is", "are", "was", "were", "to", "of", "in",
    "on", "at", "by", "for", "with", "from", "that", "this", "these", "those",
    "what", "when", "where", "who", "whom", "which", "how", "can", "you", "tell",
    "show", "explain", "about", "all", "any", "may", "will", "shall", "under",
    "have", "has", "had", "been", "does", "did", "not", "but", "look", "into",
    "whose", "would", "could", "should", "name",
}


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
        for attempt in range(3):
            try:
                resp = completion(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    api_key=self.api_key,
                    temperature=0.2,
                    max_tokens=800,
                    metadata={
                        "trace_name": "docvane-rag-answer",
                        "tags": ["docvane", "rag", "generation"],
                    },
                )
                response = cast(ModelResponse, resp)
                content = (response.choices[0].message.content or "").strip()
                if content:
                    return content
            except Exception as e:
                err_str = str(e).lower()
                logger.warning("LLM attempt %d failed in AnswerGenerator: %s", attempt + 1, str(e))
                if attempt < 2 and any(k in err_str for k in ("429", "rate", "quota", "resource_exhausted")):
                    time.sleep(2.5 * (attempt + 1))
                    continue
                elif attempt < 2:
                    time.sleep(1.0)
                    continue
                break
        return ""

    def build_prompt(self, question: str, chunks: list[dict[str, Any]]) -> str:
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
        return (
            "You are Docvane, an intelligent document analysis and RAG assistant.\n"
            "Your objective is to directly, accurately, and concisely answer the user's question "
            "using ONLY the provided context passages below.\n\n"
            "Strict Guidelines:\n"
            "1. Answer the question directly and cleanly without unnecessary preamble or repeating raw file headers.\n"
            "2. When asked for a person, role, team member, or specific responsibility (such as website, web development, backend, or project lead), "
            "directly identify the individual and their title: e.g. '**Name** - Role' [Source X].\n"
            "3. Understand domain terminology and tech stacks: for example, website or web application corresponds to MERN Stack Developer, Frontend Developer, or Fullstack Developer; "
            "mobile corresponds to App or Mobile Developer; project leader corresponds to Project Lead or AI/ML Developer & Project Lead.\n"
            "4. Format structured lists (names, roles, deliverables, dates, financial amounts, or terms) as clean Markdown bullet points.\n"
            "5. Cite the source for each claim using brackets, e.g., [Source 1] or [Page 1].\n"
            "6. If the requested information is not mentioned in the context, clearly state that it was not found in the documents.\n\n"
            f"Context Passages:\n{context_text}\n\n"
            f"User Question: {question}\n\n"
            "Direct Structured Answer:"
        )

    def stream_answer(self, question: str, chunks: list[dict[str, Any]]):
        if not chunks:
            yield (
                "I could not find relevant passages in your uploaded documents "
                "to answer this question. Please ensure your documents are uploaded and indexed."
            )
            return

        if not self.api_key:
            yield self.generate(question, chunks)
            return

        prompt = self.build_prompt(question, chunks)
        for attempt in range(3):
            try:
                resp = completion(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    api_key=self.api_key,
                    temperature=0.2,
                    max_tokens=800,
                    stream=True,
                    metadata={
                        "trace_name": "docvane-chat-stream",
                        "tags": ["docvane", "chat", "stream"],
                    },
                )
                yielded_any = False
                for chunk in resp:
                    delta = chunk.choices[0].delta.content or ""
                    if delta:
                        yielded_any = True
                        yield delta
                if yielded_any:
                    return
            except Exception as e:
                err_str = str(e).lower()
                logger.warning("LLM streaming attempt %d failed: %s", attempt + 1, str(e))
                if attempt < 2 and any(k in err_str for k in ("429", "rate", "quota", "resource_exhausted")):
                    time.sleep(2.0 * (attempt + 1))
                    continue
                break

        fallback = self.generate(question, chunks)
        yield fallback

    def generate(self, question: str, chunks: list[dict[str, Any]]) -> str:
        """Generates a structured, concise answer from context passages."""
        if not chunks:
            return (
                "I could not find relevant passages in your uploaded documents "
                "to answer this question. Please ensure your documents are uploaded and indexed."
            )

        if self.api_key:
            prompt = self.build_prompt(question, chunks)
            llm_res = self._call_llm(prompt).strip()
            if llm_res:
                return llm_res

        # If LLM call could not be completed, synthesize a clean structured extraction instead of dumping raw text
        top_chunk = chunks[0]
        top_page = top_chunk.get("page_number", 1)
        raw = top_chunk.get("content", "")
        lines = [line.strip() for line in raw.split("\n") if line.strip() and not line.startswith("[Document:")]

        q_tokens = [w for w in re.findall(r"\w{3,}", question.lower()) if w not in STOP_WORDS]
        matched_lines = []
        for line in lines:
            line_lower = line.lower()
            if any(t in line_lower for t in q_tokens) or any(
                k in line_lower
                for k in ("developer", "lead", "member", "role", "mern", "backend", "stack", "team")
            ):
                matched_lines.append(line)

        if matched_lines:
            bullets = "\n".join(f"• {l}" for l in matched_lines[:6])
            return (
                f"Based on Page {top_page} of your document [Source 1]:\n\n"
                f"{bullets}"
            )

        clean_text = " ".join(lines[:6])
        return (
            f"Based on Page {top_page} of your document [Source 1]:\n\n"
            f"{clean_text[:250]}..."
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
