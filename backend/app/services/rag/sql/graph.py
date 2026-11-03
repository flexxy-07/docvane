import logging
from typing import Any, cast

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.services.rag.sql.nodes import (
    execute_sql_node,
    explain_result_node,
    generate_sql_node,
    validate_sql_node,
)
from backend.app.services.rag.sql.state import SqlState

logger = logging.getLogger(__name__)


def decide_after_validation(state: SqlState) -> str:
    """
    Evaluates validation output:
    - If validation failed and retries remain: loop back to generate_sql with error.
    - If valid or max retries reached: proceed to execute_sql.
    """
    val_error = state.get("validation_error")
    retries = state.get("retry_count", 0)

    if val_error and retries < 2:
        logger.info(
            "Validation failed ('%s'); retrying SQL generation (attempt %d/2)...",
            val_error,
            retries,
        )
        return "generate_sql"

    return "execute_sql"


def decide_after_execution(state: SqlState) -> str:
    """
    Evaluates DB execution output:
    - If execution failed with SQL error and retries remain: loop back to generate_sql.
    - Otherwise: proceed to natural language result explanation.
    """
    exec_error = state.get("execution_error")
    retries = state.get("retry_count", 0)

    if exec_error and retries < 2:
        logger.info(
            "Execution failed ('%s'); retrying SQL generation (attempt %d/2)...",
            exec_error,
            retries,
        )
        return "generate_sql"

    return "explain_result"


def build_sql_subgraph() -> CompiledStateGraph[Any, Any, Any, Any]:
    """
    Assembles and compiles the Text-to-SQL agent sub-graph:
    generate_sql -> validate_sql -> execute_sql -> explain_result.
    Enforces retry loops on validation or execution failures up to 2 attempts.
    """
    workflow = StateGraph(cast(Any, SqlState))

    # Register nodes
    workflow.add_node("generate_sql", generate_sql_node)
    workflow.add_node("validate_sql", validate_sql_node)
    workflow.add_node("execute_sql", execute_sql_node)
    workflow.add_node("explain_result", explain_result_node)

    # Wire edges
    workflow.add_edge(START, "generate_sql")
    workflow.add_edge("generate_sql", "validate_sql")

    # Conditional edge after validation
    workflow.add_conditional_edges(
        "validate_sql",
        decide_after_validation,
        {
            "generate_sql": "generate_sql",
            "execute_sql": "execute_sql",
        },
    )

    # Conditional edge after execution
    workflow.add_conditional_edges(
        "execute_sql",
        decide_after_execution,
        {
            "generate_sql": "generate_sql",
            "explain_result": "explain_result",
        },
    )

    workflow.add_edge("explain_result", END)

    return workflow.compile()


# Compiled singleton SQL agent sub-graph
sql_agent = build_sql_subgraph()


async def execute_sql_pipeline(
    question: str,
    tenant_id: str,
    session: AsyncSession | None = None,
) -> SqlState:
    """
    Convenience orchestrator for invoking the Text-to-SQL agent sub-graph.
    """
    initial_state: SqlState = {
        "question": question,
        "tenant_id": tenant_id,
        "retry_count": 0,
        "node_latencies": {},
    }

    config = {
        "recursion_limit": 10,
        "configurable": {
            "session": session,
        },
    }

    result = await sql_agent.ainvoke(initial_state, config=config)
    return cast(SqlState, result)
