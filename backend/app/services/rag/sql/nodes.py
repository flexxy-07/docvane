import logging
import re
import time
from typing import Any, cast

from langchain_core.runnables import RunnableConfig
from litellm import completion
from litellm.types.utils import ModelResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.services.rag.sql.schema import (
    DATABASE_SCHEMA_DESCRIPTION,
    FEW_SHOT_SQL_EXAMPLES,
)
from backend.app.services.rag.sql.state import SqlState
from backend.app.services.rag.sql.validator import SqlValidator

logger = logging.getLogger(__name__)


class SqlGenerator:
    """
    Synthesizes PostgreSQL queries from natural language business inquiries.
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
                max_tokens=300,
                metadata={
                    "trace_name": "docvane-text-to-sql",
                    "tags": ["docvane", "rag", "text-to-sql"],
                },
            )
            response = cast(ModelResponse, resp)
            return (response.choices[0].message.content or "").strip()
        except Exception as e:
            logger.error("LLM call failed in SqlGenerator: %s", str(e))
            return ""

    def generate(
        self,
        question: str,
        tenant_id: str,
        error_context: str | None = None,
    ) -> str:
        if self.api_key:
            examples_text = "\n\n".join(
                f"Question: {ex['question']}\nSQL: {ex['sql'].format(tenant_id=tenant_id)}"
                for ex in FEW_SHOT_SQL_EXAMPLES
            )

            error_instruction = ""
            if error_context:
                error_instruction = (
                    f"\nPREVIOUS ATTEMPT FAILED WITH ERROR:\n{error_context}\n"
                    "Please fix the SQL query to resolve this error.\n"
                )

            prompt = (
                f"{DATABASE_SCHEMA_DESCRIPTION.format(tenant_id=tenant_id)}\n\n"
                f"EXAMPLES:\n{examples_text}\n"
                f"{error_instruction}\n"
                f"User Question: {question}\n"
                "SQL Query:"
            )
            llm_res = self._call_llm(prompt)
            if llm_res:
                return llm_res

        # Deterministic offline heuristic generator
        q_lower = question.lower()

        # Check for count invoices
        if "how many invoices" in q_lower or "count" in q_lower and "invoices" in q_lower:
            return (
                f"SELECT COUNT(*) AS invoice_count "
                f"FROM invoices WHERE tenant_id = '{tenant_id}' LIMIT 100;"
            )

        # Check for total / sum invoiced
        if "total" in q_lower or "sum" in q_lower:
            if "tax" in q_lower:
                return (
                    f"SELECT COALESCE(SUM(tax_amount), 0.0) AS total_tax "
                    f"FROM invoices WHERE tenant_id = '{tenant_id}' LIMIT 100;"
                )
            year_match = re.search(r"\b(20\d\d)\b", question)
            year_filter = f" AND invoice_date LIKE '{year_match.group(1)}%'" if year_match else ""
            return (
                f"SELECT COALESCE(SUM(total_amount), 0.0) AS total_invoiced "
                f"FROM invoices WHERE tenant_id = '{tenant_id}'{year_filter} LIMIT 100;"
            )

        # Check for contracts
        if "contracts" in q_lower:
            return (
                f"SELECT COUNT(*) AS contract_count "
                f"FROM contracts WHERE tenant_id = '{tenant_id}' LIMIT 100;"
            )

        # Default fallback query
        return (
            f"SELECT id, filename, doc_type, status "
            f"FROM documents WHERE tenant_id = '{tenant_id}' LIMIT 10;"
        )


def generate_sql_node(state: SqlState) -> SqlState:
    """
    LangGraph node: Generates SQL query from user question and schema descriptions.
    Incorporates error context if looping on a retry.
    """
    t0 = time.perf_counter()
    generator = SqlGenerator()
    question = state.get("question", "")
    tenant_id = state.get("tenant_id", "")
    error_context = state.get("validation_error") or state.get("execution_error")

    sql = generator.generate(question, tenant_id, error_context=error_context)
    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 3)

    latencies = state.get("node_latencies", {}).copy()
    latencies["generate_sql_node"] = elapsed_ms

    logger.info("generate_sql_node created query in %.3fms: %s", elapsed_ms, sql)
    return {
        **state,
        "sql_query": sql,
        "node_latencies": latencies,
    }


def validate_sql_node(state: SqlState) -> SqlState:
    """
    LangGraph node: Verifies SQL query against security guardrails.
    """
    t0 = time.perf_counter()
    validator = SqlValidator()
    sql = state.get("sql_query") or ""
    tenant_id = state.get("tenant_id", "")

    result = validator.validate_and_sanitize(sql, tenant_id)
    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 3)

    latencies = state.get("node_latencies", {}).copy()
    latencies["validate_sql_node"] = elapsed_ms

    if result.is_valid:
        logger.info("validate_sql_node approved query in %.3fms", elapsed_ms)
        return {
            **state,
            "sql_query": result.sanitized_sql,
            "validation_error": None,
            "node_latencies": latencies,
        }

    logger.warning("validate_sql_node rejected query: %s", result.error)
    retries = state.get("retry_count", 0) + 1
    return {
        **state,
        "validation_error": result.error,
        "retry_count": retries,
        "node_latencies": latencies,
    }


async def execute_sql_node(
    state: SqlState,
    config: RunnableConfig | None = None,
) -> SqlState:
    """
    LangGraph node: Safely executes validated read-only SQL query with timeout and row limits.
    """
    t0 = time.perf_counter()
    conf = config.get("configurable", {}) if config else {}
    session: AsyncSession | None = conf.get("session")

    sql = state.get("sql_query", "")
    results: list[dict[str, Any]] = []
    exec_error: str | None = None

    if session and sql:
        try:
            db_res = await session.execute(text(sql))
            rows = db_res.mappings().all()
            results = [dict(r) for r in rows]
        except Exception as exc:
            exec_error = str(exc)
            logger.error("execute_sql_node execution failed: %s", exec_error)
    else:
        # Offline or mock fallback
        results = state.get("sql_results") or []

    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 3)
    latencies = state.get("node_latencies", {}).copy()
    latencies["execute_sql_node"] = elapsed_ms

    retries = state.get("retry_count", 0)
    if exec_error:
        retries += 1

    return {
        **state,
        "sql_results": results,
        "execution_error": exec_error,
        "retry_count": retries,
        "node_latencies": latencies,
    }


def explain_result_node(state: SqlState) -> SqlState:
    """
    LangGraph node: Explains quantitative results in natural language and displays the SQL query.
    """
    t0 = time.perf_counter()
    sql = state.get("sql_query", "")
    results = state.get("sql_results", [])
    validation_err = state.get("validation_error")
    execution_err = state.get("execution_error")

    if validation_err:
        explanation = (
            f"Unable to process query due to a security validation rule: {validation_err}"
        )
    elif execution_err:
        explanation = f"Database query failed to execute: {execution_err}"
    elif not results:
        explanation = (
            "The query executed successfully, but found 0 matching records in your documents.\n\n"
            f"```sql\n{sql}\n```"
        )
    else:
        # Format the top figures into readable markdown
        row = results[0]
        formatted_items: list[str] = []
        for k, v in row.items():
            if isinstance(v, float):
                is_money = any(m in k for m in ("amount", "total", "tax", "subtotal", "cost"))
                val_str = f"${v:,.2f}" if is_money else f"{v:,.2f}"
            elif isinstance(v, int):
                val_str = f"{v:,}"
            else:
                val_str = str(v)
            formatted_items.append(f"**{k}**: {val_str}")

        details = ", ".join(formatted_items)
        explanation = (
            f"Based on your structured document records, {details}.\n\n"
            f"**Executed SQL Query:**\n```sql\n{sql}\n```"
        )

    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 3)
    latencies = state.get("node_latencies", {}).copy()
    latencies["explain_result_node"] = elapsed_ms

    return {
        **state,
        "explanation": explanation,
        "node_latencies": latencies,
    }
