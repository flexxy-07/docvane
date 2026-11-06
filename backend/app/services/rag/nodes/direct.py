import logging
import re
import time

from backend.app.services.rag.state import RagState

logger = logging.getLogger(__name__)

CAPABILITIES_OVERVIEW = (
    "I am **Docvane**, your document assistant. "
    "Here is what I can do:\n\n"
    "1. **Contract Analysis**: Ask about liability caps, indemnification, termination clauses, "
    "and governing law with page-level citations.\n"
    "2. **Invoice Intelligence**: Query invoice numbers, line items, due dates, totals, "
    "and tax breakdowns.\n"
    "3. **Hybrid Search**: Combine pgvector semantic embeddings with full-text keyword search "
    "and cross-encoder reranking.\n"
    "4. **Quantitative Aggregations**: Ask for totals, counts, and sums across documents.\n\n"
    "How can I assist you with your business documents today?"
)


def direct_answer_node(state: RagState) -> RagState:
    """
    LangGraph node: Directly responds to conversational greetings,
    system capabilities, and general assistance queries without hitting the database.
    """
    t0 = time.perf_counter()
    question = state.get("question", "").strip().lower()

    if re.search(r"^(hi|hello|hey|greetings|good\s+(morning|afternoon|evening))\b", question):
        answer = (
            "Hello! I am Docvane, your AI document assistant. "
            "You can upload invoices and contracts, ask questions about specific clauses, "
            "or run quantitative searches across your files. How can I help you today?"
        )
    elif re.search(r"\b(thank\s+you|thanks|bye|goodbye)\b", question):
        answer = "You're welcome! Feel free to ask whenever you need help with your documents."
    elif re.search(
        r"\b(who\s+are\s+you|what\s+can\s+you\s+do|how\s+do\s+you\s+work|help)\b", question
    ):
        answer = CAPABILITIES_OVERVIEW
    else:
        answer = (
            "I am ready to help with your documents! Please upload contracts or invoices, "
            "or ask questions regarding your uploaded records."
        )


    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 3)
    latencies = state.get("node_latencies", {}).copy()
    latencies["direct_answer_node"] = elapsed_ms

    logger.info("Direct answer node completed in %.3fms", elapsed_ms)

    return {
        **state,
        "answer": answer,
        "citations": [],
        "node_latencies": latencies,
    }
