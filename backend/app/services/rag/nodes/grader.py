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
    "have", "has", "had", "been", "does", "did", "not", "but",
}


class PassageGrader:
    """
    Evaluates retrieved chunks for relevance to the user's question (CRAG pattern).
    Filters out distractor or irrelevant passages.
    """

    def __init__(
        self,
        model_name: str | None = None,
        api_key: str | None = None,
        score_threshold: float = 0.35,
    ) -> None:
        self.model: str = model_name or settings.DEFAULT_LLM_MODEL
        self.api_key: str | None = (
            api_key if api_key is not None else (settings.GEMINI_API_KEY or None)
        )
        self.score_threshold = score_threshold

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
            logger.error("LLM call failed in PassageGrader: %s", str(e))
            return ""

    def grade_chunk(self, question: str, chunk_content: str, score: float = 0.0) -> bool:
        """
        Grades an individual passage as relevant (True) or irrelevant (False).
        """
        if self.api_key:
            prompt = (
                "You are an expert evaluator assessing relevance of a retrieved document passage "
                "to a user's question in a business contract/invoice intelligence system.\n\n"
                f"Question: {question}\n\n"
                f"Passage: {chunk_content}\n\n"
                "Is the passage relevant to answering the question? "
                "Respond ONLY with 'yes' or 'no'."
            )
            llm_res = self._call_llm(prompt)
            if "yes" in llm_res:
                return True
            if "no" in llm_res:
                return False

        # Deterministic offline fallback:
        # Pass if cross-encoder score meets threshold or meaningful keyword overlap exists
        if score >= self.score_threshold:
            return True

        q_words = set(re.findall(r"\w{3,}", question.lower())) - STOP_WORDS
        c_words = set(re.findall(r"\w{3,}", chunk_content.lower())) - STOP_WORDS
        common = q_words.intersection(c_words)
        return len(common) >= 1


def grade_passages_node(state: RagState) -> RagState:
    """
    LangGraph node: Evaluates each retrieved chunk.
    Keeps only relevant chunks. If no relevant chunks remain, sets grade to 'irrelevant'
    to trigger the corrective query rewrite loop.
    """
    t0 = time.perf_counter()
    grader = PassageGrader()
    question = state.get("question", "")
    chunks: list[dict[str, Any]] = state.get("retrieved_chunks", [])

    relevant_chunks: list[dict[str, Any]] = []
    for c in chunks:
        content = c.get("content", "")
        raw_score = c.get("score", 0.0)
        score = float(raw_score) if isinstance(raw_score, (int, float)) else 0.0
        if grader.grade_chunk(question, content, score=score):
            relevant_chunks.append(c)

    grade = "relevant" if relevant_chunks else "irrelevant"
    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 3)

    latencies = state.get("node_latencies", {}).copy()
    latencies["grade_passages_node"] = elapsed_ms

    logger.info(
        "grade_passages_node: %d/%d chunks deemed relevant (grade='%s') in %.3fms",
        len(relevant_chunks),
        len(chunks),
        grade,
        elapsed_ms,
    )

    return {
        **state,
        "grade": grade,
        "retrieved_chunks": relevant_chunks,
        "node_latencies": latencies,
    }
