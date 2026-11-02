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
    "have", "has", "had", "been", "does", "did", "not", "but", "based", "document",
}


class AnswerSupportGrader:
    """
    Self-RAG grader: Evaluates whether the generated answer is fully grounded
    in the retrieved passages, preventing hallucinations.
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
                temperature=0.0,
                max_tokens=20,
            )
            response = cast(ModelResponse, resp)
            return (response.choices[0].message.content or "").strip().lower()
        except Exception as e:
            logger.error("LLM call failed in AnswerSupportGrader: %s", str(e))
            return ""

    def grade_support(self, answer: str | None, chunks: list[dict[str, Any]]) -> bool:
        """
        Returns True if answer is grounded in the chunks, False if hallucinated.
        """
        if not answer or not answer.strip():
            return False

        if not chunks:
            # If no chunks exist, an answer claiming facts is unsupported
            return "could not find relevant passages" in answer.lower()

        context = "\n\n".join(c.get("content", "") for c in chunks)

        if self.api_key:
            prompt = (
                "You are an expert fact-checker in a document intelligence system. "
                "Assess whether the generated answer is strictly grounded in and supported "
                "by the context passages below.\n\n"
                f"Context Passages:\n{context}\n\n"
                f"Generated Answer:\n{answer}\n\n"
                "Is the answer grounded in the facts from the passages? "
                "Respond ONLY with 'yes' or 'no'."
            )
            llm_res = self._call_llm(prompt)
            if "yes" in llm_res:
                return True
            if "no" in llm_res:
                return False

        # Deterministic offline fallback:
        # Check that substantive content words in answer appear in the context
        ans_words = set(re.findall(r"\w{4,}", answer.lower())) - STOP_WORDS
        ctx_words = set(re.findall(r"\w{4,}", context.lower())) - STOP_WORDS

        if not ans_words:
            return True

        grounded_count = len(ans_words.intersection(ctx_words))
        ratio = grounded_count / len(ans_words)
        return ratio >= 0.4


def check_answer_support_node(state: RagState) -> RagState:
    """
    LangGraph node: Self-RAG grounding check.
    If the answer is supported by the chunks, marks state["grade"] = "supported".
    If unsupported (hallucination detected), marks state["grade"] = "unsupported".
    """
    t0 = time.perf_counter()
    grader = AnswerSupportGrader()
    answer = state.get("answer") or ""
    chunks: list[dict[str, Any]] = state.get("retrieved_chunks", [])

    is_supported = grader.grade_support(answer, chunks)
    grade = "supported" if is_supported else "unsupported"

    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 3)
    latencies = state.get("node_latencies", {}).copy()
    latencies["check_answer_support_node"] = elapsed_ms

    logger.info("check_answer_support_node: grade='%s' in %.3fms", grade, elapsed_ms)

    return {
        **state,
        "grade": grade,
        "node_latencies": latencies,
    }
