import logging
import re
import time
from typing import Literal

from backend.app.services.rag.state import RagState

logger = logging.getLogger(__name__)

RouteType = Literal["direct", "simple", "transform", "sql", "both"]


class QueryRouter:
    """
    Classifies incoming user questions to determine the optimal processing path:
    1. 'direct': Greetings, meta-queries, or chitchat (no DB/retrieval needed).
    2. 'sql': Quantitative aggregations, counts, sums, and totals over structured records.
    3. 'both': Inquiries needing both SQL aggregates and document clause explanations.
    4. 'simple': Targeted, single-fact document lookups (runs direct hybrid search).
    5. 'transform': Broad, complex, or multi-faceted queries needing query rewriting or HyDE.
    """

    # Direct greetings / non-retrieval queries
    DIRECT_PATTERNS = [
        r"^(hi|hello|hey|greetings|good\s+(morning|afternoon|evening))\b",
        r"^(who\s+are\s+you|what\s+can\s+you\s+do|how\s+do\s+you\s+work|help)\b",
        r"^(thank\s+you|thanks|bye|goodbye)\b",
    ]

    # SQL / Aggregation keywords (sums, counts, totals over structured tables)
    SQL_PATTERNS = [
        r"\b(total\s+(amount|invoiced|spent|cost|paid|tax|subtotal))\b",
        r"\b(how\s+many\s+(invoices|contracts|documents|bills|receipts))\b",
        r"\b(sum\s+of|average\s+(amount|total)|highest|lowest|minimum|maximum)\b",
        r"\b(count\s+(all\s+)?(invoices|contracts))\b",
    ]

    # Qualitative document clauses / text terms
    QUALITATIVE_PATTERNS = [
        r"\b(explain|summarize|what\s+do\s+the\s+terms\s+say|clauses?|obligations?)\b",
        r"\b(payment\s+terms|governing\s+law|termination|liability|indemnif\w+)\b",
    ]

    # Complex / broad transform cues
    TRANSFORM_PATTERNS = [
        r"\b(compare|contrast|difference\s+between|overview|all\s+potential)\b",
        r"\b(pros\s+and\s+cons|risks?\s+and|liabilit\w+|comprehensive)\b",
        r"\b(what\s+happens\s+if|in\s+case\s+of|under\s+what\s+circumstances)\b",
    ]

    def classify(self, question: str) -> RouteType:
        """Classifies a question string into one of the 5 execution routes."""
        q = question.strip().lower()

        # 1. Check for direct conversational questions
        for pattern in self.DIRECT_PATTERNS:
            if re.search(pattern, q):
                return "direct"

        has_sql = any(bool(re.search(pat, q)) for pat in self.SQL_PATTERNS)
        has_qualitative = any(bool(re.search(pat, q)) for pat in self.QUALITATIVE_PATTERNS)

        # 2. Check for hybrid 'both' (e.g. "Total invoiced by Acme and what do payment terms say?")
        if has_sql and has_qualitative:
            return "both"

        # 3. Check for pure SQL aggregations
        if has_sql:
            return "sql"

        # 4. Check for complex transform queries
        if any(bool(re.search(pat, q)) for pat in self.TRANSFORM_PATTERNS):
            return "transform"

        # 5. Default: targeted simple document lookup
        return "simple"


def router_node(state: RagState) -> RagState:
    """
    LangGraph node: Inspects the user's question, assigns the route to state,
    and records node execution latency.
    """
    t0 = time.perf_counter()
    router = QueryRouter()
    question = state.get("question", "")

    route = router.classify(question)
    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 3)

    latencies = state.get("node_latencies", {}).copy()
    latencies["router_node"] = elapsed_ms

    logger.info("Classified question '%s' -> route '%s' in %.3fms", question, route, elapsed_ms)

    return {
        **state,
        "route": route,
        "node_latencies": latencies,
    }
