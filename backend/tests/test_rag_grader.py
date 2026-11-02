from unittest.mock import patch

from backend.app.services.rag.nodes.grader import PassageGrader, grade_passages_node
from backend.app.services.rag.state import RagState


def test_passage_grader_offline_relevant() -> None:
    grader = PassageGrader(api_key=None)
    question = "What is the liability cap under this agreement?"
    chunk = "In no event shall either party's aggregate liability exceed $1,000,000."

    is_relevant = grader.grade_chunk(question, chunk, score=0.88)
    assert is_relevant is True


def test_passage_grader_offline_irrelevant() -> None:
    grader = PassageGrader(api_key=None)
    question = "What is the invoice number on the Acme PDF?"
    chunk = "The cafeteria serves lunch from 12pm to 2pm on weekdays."

    is_relevant = grader.grade_chunk(question, chunk, score=0.02)
    assert is_relevant is False


def test_passage_grader_mocked_llm() -> None:
    grader = PassageGrader(api_key="mock-key")

    with patch.object(grader, "_call_llm") as mock_call:
        mock_call.return_value = "yes"
        assert grader.grade_chunk("Any question", "Any passage") is True

        mock_call.return_value = "no"
        assert grader.grade_chunk("Any question", "Any passage") is False


def test_grade_passages_node_mixed_chunks() -> None:
    initial_state: RagState = {
        "question": "What are the payment terms?",
        "tenant_id": "00000000-0000-0000-0000-000000000001",
        "retrieved_chunks": [
            {
                "chunk_id": "1",
                "content": "Payment terms shall be net 45 days after receipt of valid invoice.",
                "score": 0.82,
            },
            {
                "chunk_id": "2",
                "content": "Employees may park in the visitor lot only on weekends.",
                "score": 0.05,
            },
        ],
        "node_latencies": {},
    }

    new_state = grade_passages_node(initial_state)

    assert new_state["grade"] == "relevant"
    assert len(new_state["retrieved_chunks"]) == 1
    assert new_state["retrieved_chunks"][0]["chunk_id"] == "1"
    assert "grade_passages_node" in new_state["node_latencies"]


def test_grade_passages_node_all_irrelevant() -> None:
    initial_state: RagState = {
        "question": "What are the payment terms?",
        "tenant_id": "00000000-0000-0000-0000-000000000001",
        "retrieved_chunks": [
            {
                "chunk_id": "99",
                "content": "General office supplies are kept in storage room B.",
                "score": 0.01,
            }
        ],
        "node_latencies": {},
    }

    new_state = grade_passages_node(initial_state)

    assert new_state["grade"] == "irrelevant"
    assert len(new_state["retrieved_chunks"]) == 0
    assert "grade_passages_node" in new_state["node_latencies"]
