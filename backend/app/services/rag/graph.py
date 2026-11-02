import logging
from typing import Any, cast

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.services.rag.nodes.direct import direct_answer_node
from backend.app.services.rag.nodes.generation import generate_node
from backend.app.services.rag.nodes.grader import grade_passages_node
from backend.app.services.rag.nodes.retrieval import retrieve_node
from backend.app.services.rag.nodes.router import router_node
from backend.app.services.rag.nodes.support import check_answer_support_node
from backend.app.services.rag.nodes.transform import transform_query_node
from backend.app.services.rag.state import RagState

logger = logging.getLogger(__name__)


def route_decision(state: RagState) -> str:
    """
    Evaluates state["route"] to select the initial processing branch:
    - "direct": Greetings, help, meta queries -> direct_answer
    - "transform" or "both": Complex queries needing multi-query expansion -> transform_query
    - "simple" or "sql": Direct targeted search -> retrieve
    """
    route = state.get("route", "simple")
    if route == "direct":
        return "direct_answer"
    if route in ("transform", "both"):
        return "transform_query"
    return "retrieve"


def decide_after_grading(state: RagState) -> str:
    """
    CRAG decision function:
    - If retrieved passages are graded 'relevant' or max retries reached: proceed to generate.
    - If all passages are 'irrelevant' and retries remaining: loop back to transform_query.
    """
    grade = state.get("grade")
    retry_count = state.get("retry_count", 0)

    if grade == "relevant" or retry_count >= 2:
        return "generate"

    logger.info("Retrying query transformation (attempt %d/2)...", retry_count + 1)
    return "transform_query"


def build_rag_graph() -> CompiledStateGraph[Any, Any, Any, Any]:
    """
    Assembles and compiles the Self-Correcting StateGraph for the Docvane RAG pipeline:
    1. router -> classifies query
    2. direct_answer -> shortcuts conversational queries
    3. transform_query -> multi-query / rewrite / HyDE
    4. retrieve -> pgvector + tsvector + RRF + cross-encoder rerank
    5. grade_passages -> CRAG filtering & retry loop
    6. generate -> grounded synthesis with citations
    7. check_answer_support -> Self-RAG hallucination validation
    """
    workflow = StateGraph(cast(Any, RagState))

    # Register nodes
    workflow.add_node("router", router_node)
    workflow.add_node("direct_answer", direct_answer_node)
    workflow.add_node("transform_query", transform_query_node)
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("grade_passages", grade_passages_node)
    workflow.add_node("generate", generate_node)
    workflow.add_node("check_answer_support", check_answer_support_node)

    # Initial routing
    workflow.add_edge(START, "router")
    workflow.add_conditional_edges(
        "router",
        route_decision,
        {
            "direct_answer": "direct_answer",
            "retrieve": "retrieve",
            "transform_query": "transform_query",
        },
    )

    # Direct answers complete immediately
    workflow.add_edge("direct_answer", END)

    # Retrieval feeds into passage grading
    workflow.add_edge("transform_query", "retrieve")
    workflow.add_edge("retrieve", "grade_passages")

    # CRAG conditional edge: generate OR corrective loop back to transform_query
    workflow.add_conditional_edges(
        "grade_passages",
        decide_after_grading,
        {
            "generate": "generate",
            "transform_query": "transform_query",
        },
    )

    # Generation feeds into Self-RAG answer support check
    workflow.add_edge("generate", "check_answer_support")
    workflow.add_edge("check_answer_support", END)

    return workflow.compile()


# Singleton compiled graph instance
rag_pipeline: CompiledStateGraph[Any, Any, Any, Any] = build_rag_graph()


async def execute_rag_pipeline(
    question: str,
    tenant_id: str,
    session: AsyncSession | None = None,
    retrieval_service: Any | None = None,
    top_k: int = 5,
    max_retries: int = 2,
) -> RagState:
    """
    Convenience orchestrator for invoking the compiled LangGraph RAG pipeline.
    Enforces recursion limits and tracks state through corrective feedback loops.
    """
    initial_state: RagState = {
        "question": question,
        "tenant_id": tenant_id,
        "node_latencies": {},
        "retry_count": 0,
    }

    config = {
        "recursion_limit": 15,
        "configurable": {
            "session": session,
            "retrieval_service": retrieval_service,
            "top_k": top_k,
            "max_retries": max_retries,
        },
    }

    result = await rag_pipeline.ainvoke(initial_state, config=config)
    return cast(RagState, result)


