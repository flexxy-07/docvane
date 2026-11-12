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

SYNONYMS: dict[str, set[str]] = {
    "website": {"mern", "react", "frontend", "web", "html", "css", "javascript", "developer", "stack", "ui"},
    "web": {"mern", "react", "frontend", "website", "html", "developer", "fullstack", "ui"},
    "mobile": {"react native", "android", "ios", "app", "application", "mobile", "developer"},
    "app": {"application", "mobile", "software", "developer", "react native", "android", "ios"},
    "leader": {"lead", "head", "manager", "director", "project lead"},
    "lead": {"leader", "head", "manager", "project lead", "lead"},
    "backend": {"backend", "api", "database", "python", "node", "server", "fastapi"},
    "team": {"members", "developer", "lead", "engineer", "roles", "name"},
    "members": {"team", "developer", "lead", "engineer", "roles", "name", "member"},
    "member": {"team", "developer", "lead", "engineer", "roles", "name", "members"},
}


class PassageGrader:
    """
    Evaluates retrieved chunks for relevance to the user's question (CRAG pattern).
    Filters out distractor or irrelevant passages while preserving conceptually matching
    passages to prevent false negatives.
    """

    def __init__(
        self,
        model_name: str | None = None,
        api_key: str | None = None,
        score_threshold: float = 0.15,
    ) -> None:
        self.model: str = model_name or settings.DEFAULT_LLM_MODEL
        self.api_key: str | None = (
            api_key if api_key is not None else (settings.effective_gemini_api_key or None)
        )
        self.score_threshold = score_threshold

    def _call_llm(self, prompt: str) -> str:
        if not self.api_key:
            return ""
        for attempt in range(2):
            try:
                resp = completion(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    api_key=self.api_key,
                    temperature=0.0,
                    max_tokens=20,
                    metadata={
                        "trace_name": "docvane-passage-grader",
                        "tags": ["docvane", "rag", "grader"],
                    },
                )
                response = cast(ModelResponse, resp)
                return (response.choices[0].message.content or "").strip().lower()
            except Exception as e:
                logger.warning("LLM call attempt %d failed in PassageGrader: %s", attempt + 1, str(e))
                if attempt == 0:
                    time.sleep(1.0)
        return ""

    def grade_chunk(self, question: str, chunk_content: str, score: float = 0.0) -> bool:
        """
        Grades an individual passage as relevant (True) or irrelevant (False).
        Uses score thresholds and semantic/lexical overlap first to prevent
        unnecessary API rate-limit consumption.
        """
        # 1. Reranker/hybrid confidence score meets threshold
        if score >= self.score_threshold:
            return True

        q_words = set(re.findall(r"\w{3,}", question.lower())) - STOP_WORDS
        c_words = set(re.findall(r"\w{3,}", chunk_content.lower())) - STOP_WORDS

        # 2. Direct lexical overlap
        common = q_words.intersection(c_words)
        if len(common) >= 1:
            return True

        # 3. Synonym / conceptual role mapping (e.g., website -> MERN, web)
        for q_word in q_words:
            syns = SYNONYMS.get(q_word, set())
            if syns.intersection(c_words):
                return True

        # 4. LLM-based evaluation for ambiguous cases
        if self.api_key:
            prompt = (
                "You are an evaluator assessing if a document excerpt is relevant or contains "
                "helpful context to answer a user's question across technical, business, or operational documents.\n"
                "Consider conceptual matches, synonyms (e.g., web/website matching MERN or frontend, "
                "mobile matching app, lead matching leader), and role assignments as relevant.\n\n"
                f"Question: {question}\n\n"
                f"Passage: {chunk_content}\n\n"
                "Is the passage relevant or helpful to answering the question? "
                "Respond ONLY with 'yes' or 'no'."
            )
            llm_res = self._call_llm(prompt)
            if "yes" in llm_res:
                return True
            if "no" in llm_res:
                return False

        return False


def grade_passages_node(state: RagState) -> RagState:
    """
    LangGraph node: Evaluates each retrieved chunk.
    Keeps only relevant chunks. If strict grading eliminates all candidates but
    chunks were retrieved, preserves the top candidates to avoid false negatives.
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

    # Prevent total context erasure when retriever found indexed document candidates
    if not relevant_chunks and chunks:
        logger.info(
            "grade_passages_node: zero chunks passed strict check; retaining top %d candidates for answer generation",
            min(3, len(chunks)),
        )
        relevant_chunks = chunks[:3]

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
