from unittest.mock import patch

from backend.app.services.rag.nodes.transform import QueryTransformer, transform_query_node
from backend.app.services.rag.state import RagState


def test_rewrite_query_offline_fallback() -> None:
    transformer = QueryTransformer(api_key=None)

    q1 = "Can you please explain the payment terms?"
    clean1 = transformer.rewrite_query(q1)
    assert clean1.lower() == "payment terms"

    q2 = "What is the liability cap under this agreement?"
    clean2 = transformer.rewrite_query(q2)
    assert "liability cap" in clean2.lower()

    q3 = "Can you show me the termination notice period?"
    clean3 = transformer.rewrite_query(q3)
    assert clean3.lower() == "termination notice period"


def test_expand_queries_offline_fallback() -> None:
    transformer = QueryTransformer(api_key=None)

    question = "Can you please tell me about late payment penalties?"
    variants = transformer.expand_queries(question)

    assert len(variants) == 3
    assert variants[0] == question
    assert "late payment penalties" in variants[1].lower()
    assert "clauses and obligations" in variants[2].lower()


def test_generate_hyde_offline_fallback() -> None:
    transformer = QueryTransformer(api_key=None)

    question = "What are the governing law provisions?"
    passage = transformer.generate_hyde(question)

    assert "Under this agreement" in passage
    assert "governing law provisions" in passage.lower()


def test_query_transformer_with_mocked_llm() -> None:
    transformer = QueryTransformer(api_key="mock-key")

    with patch.object(transformer, "_call_llm") as mock_call:
        # 1. Test rewrite
        mock_call.return_value = ' "Acme Corp termination clause 2024" '
        rewritten = transformer.rewrite_query("Can you tell me about Acme termination?")
        assert rewritten == "Acme Corp termination clause 2024"

        # 2. Test multi-query expansion
        mock_call.return_value = (
            "1. Acme payment terms\n2. Acme invoice due date\n3. Acme late payment interest"
        )
        expanded = transformer.expand_queries("What are the payment terms for Acme?")
        assert len(expanded) == 3
        assert expanded[0] == "Acme payment terms"
        assert expanded[1] == "Acme invoice due date"
        assert expanded[2] == "Acme late payment interest"

        # 3. Test HyDE
        mock_call.return_value = (
            "This Agreement shall be governed by and construed "
            "in accordance with the laws of Delaware."
        )
        hyde = transformer.generate_hyde("What is the governing law?")
        assert "Delaware" in hyde


def test_transform_query_node_execution() -> None:
    initial_state: RagState = {
        "question": "Can you please explain the indemnification obligations?",
        "tenant_id": "00000000-0000-0000-0000-000000000001",
        "node_latencies": {},
    }

    new_state = transform_query_node(initial_state)

    assert "rewritten_queries" in new_state
    assert len(new_state["rewritten_queries"]) == 3
    assert "transform_query_node" in new_state["node_latencies"]
    assert new_state["node_latencies"]["transform_query_node"] >= 0.0
