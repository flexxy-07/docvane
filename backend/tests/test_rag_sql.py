import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.app.services.rag.sql.graph import execute_sql_pipeline
from backend.app.services.rag.sql.nodes import SqlGenerator, explain_result_node
from backend.app.services.rag.sql.state import SqlState
from backend.app.services.rag.sql.validator import SqlValidator


def test_sql_validator_allows_safe_queries() -> None:
    validator = SqlValidator()
    tenant_id = str(uuid.uuid4())

    query = (
        f"SELECT vendor_name, total_amount FROM invoices "
        f"WHERE tenant_id = '{tenant_id}' AND total_amount > 1000 LIMIT 50"
    )
    res = validator.validate_and_sanitize(query, tenant_id)
    assert res.is_valid is True
    assert res.error is None
    assert "LIMIT 50;" in res.sanitized_sql


def test_sql_validator_blocks_destructive_queries() -> None:
    validator = SqlValidator()
    tenant_id = str(uuid.uuid4())

    bad_queries = [
        "DROP TABLE invoices;",
        "DELETE FROM invoices WHERE total_amount > 0;",
        "UPDATE invoices SET total_amount = 0;",
        "INSERT INTO invoices (vendor_name) VALUES ('Hacker');",
        "TRUNCATE documents;",
        "SELECT * FROM invoices; DROP TABLE contracts;",
    ]

    for q in bad_queries:
        res = validator.validate_and_sanitize(q, tenant_id)
        assert res.is_valid is False
        assert "Security violation" in (res.error or "")


def test_sql_validator_blocks_unauthorized_tables() -> None:
    validator = SqlValidator()
    tenant_id = str(uuid.uuid4())

    forbidden_queries = [
        f"SELECT * FROM users WHERE tenant_id = '{tenant_id}';",
        f"SELECT * FROM memberships WHERE tenant_id = '{tenant_id}';",
        f"SELECT * FROM pg_catalog.pg_tables WHERE tenant_id = '{tenant_id}';",
    ]

    for q in forbidden_queries:
        res = validator.validate_and_sanitize(q, tenant_id)
        assert res.is_valid is False
        assert "Access denied" in (res.error or "") or "Security violation" in (res.error or "")


def test_sql_validator_enforces_tenant_and_limit() -> None:
    validator = SqlValidator()
    tenant_id = str(uuid.uuid4())

    # Query without tenant_id and without limit
    q = "SELECT vendor_name, total_amount FROM invoices"
    res = validator.validate_and_sanitize(q, tenant_id)
    assert res.is_valid is True
    assert f"tenant_id = '{tenant_id}'" in res.sanitized_sql
    assert "LIMIT 100;" in res.sanitized_sql


def test_sql_generator_offline_heuristics() -> None:
    generator = SqlGenerator(api_key=None)
    tenant_id = str(uuid.uuid4())

    q1 = "What is the total amount invoiced across all vendors in 2024?"
    sql1 = generator.generate(q1, tenant_id)
    assert "SUM(total_amount)" in sql1
    assert "2024%" in sql1

    q2 = "How many invoices were uploaded last month?"
    sql2 = generator.generate(q2, tenant_id)
    assert "COUNT(*)" in sql2
    assert "invoices" in sql2

    q3 = "What is the total tax paid?"
    sql3 = generator.generate(q3, tenant_id)
    assert "SUM(tax_amount)" in sql3


def test_explain_result_node_formatting() -> None:
    state: SqlState = {
        "question": "What is the total amount invoiced?",
        "sql_query": "SELECT SUM(total_amount) AS total_invoiced FROM invoices;",
        "sql_results": [{"total_invoiced": 45250.75}],
        "node_latencies": {},
    }

    new_state = explain_result_node(state)
    assert "explanation" in new_state
    assert "$45,250.75" in (new_state["explanation"] or "")
    assert "SELECT SUM(total_amount)" in (new_state["explanation"] or "")


@pytest.mark.asyncio
async def test_execute_sql_pipeline_end_to_end() -> None:
    tenant_id = str(uuid.uuid4())
    mock_session = MagicMock()
    mock_db_res = MagicMock()
    mock_db_res.mappings.return_value.all.return_value = [
        {"total_invoiced": 128500.0, "invoice_count": 14}
    ]
    mock_session.execute = AsyncMock(return_value=mock_db_res)

    result = await execute_sql_pipeline(
        question="What is the total amount invoiced in 2024?",
        tenant_id=tenant_id,
        session=mock_session,
    )

    assert result.get("sql_query") is not None
    assert f"tenant_id = '{tenant_id}'" in (result.get("sql_query") or "")
    assert result.get("sql_results") == [{"total_invoiced": 128500.0, "invoice_count": 14}]
    assert "$128,500.00" in (result.get("explanation") or "")

    latencies = result.get("node_latencies", {})
    assert "generate_sql_node" in latencies
    assert "validate_sql_node" in latencies
    assert "execute_sql_node" in latencies
    assert "explain_result_node" in latencies
