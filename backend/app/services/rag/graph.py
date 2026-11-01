import logging
from typing import Any, cast

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.services.rag.nodes.direct import direct_answer_node
from backend.app.services.rag.nodes.generation import generate_node
from backend.app.services.rag.nodes.retrieval import retrieve_node
from backend.app.services.rag.nodes.router import router_node
from backend.app.services.rag.nodes.transform import transform_query_node
from backend.app.services.rag.state import RagState

logger = logging.getLogger(__name__)


def route_decision(state: RagState) -> str:
    """
    Evaluates state["route"] to select the appropriate branch:
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


def build_rag_graph() -> CompiledStateGraph[Any, Any, Any, Any]:
    """
    Assembles and compiles the StateGraph for the Docvane RAG pipeline.
    """
    workflow = StateGraph(cast(Any, RagState))

    # Register nodes
    workflow.add_node("router", router_node)
    workflow.add_node("direct_answer", direct_answer_node)
    workflow.add_node("transform_query", transform_query_node)
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("generate", generate_node)

    # Configure graph edges
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

    # Direct answers finish immediately without DB lookup
    workflow.add_edge("direct_answer", END)

    # Transformed queries proceed to multi-query retrieval
    workflow.add_edge("transform_query", "retrieve")

    # Retrieved passages feed into answer synthesis
    workflow.add_edge("retrieve", "generate")
    workflow.add_edge("generate", END)

    return workflow.compile()


# Singleton compiled graph instance
rag_pipeline: CompiledStateGraph[Any, Any, Any, Any] = build_rag_graph()


async def execute_rag_pipeline(
    question: str,
    tenant_id: str,
    session: AsyncSession | None = None,
    retrieval_service: Any | None = None,
    top_k: int = 5,
) -> RagState:
    """
    Convenience orchestrator for invoking the compiled LangGraph RAG pipeline.
    """
    initial_state: RagState = {
        "question": question,
        "tenant_id": tenant_id,
        "node_latencies": {},
        "retry_count": 0,
    }

    config = {
        "configurable": {
            "session": session,
            "retrieval_service": retrieval_service,
            "top_k": top_k,
        }
    }

    result = await rag_pipeline.ainvoke(initial_state, config=config)
    return cast(RagState, result)

