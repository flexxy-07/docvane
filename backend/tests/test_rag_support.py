from unittest.mock import patch

from backend.app.services.rag.nodes.support import AnswerSupportGrader, check_answer_support_node
from backend.app.services.rag.state import RagState


def test_answer_support_offline_grounded() -> None:
    grader = AnswerSupportGrader(api_key=None)
    chunks = [
        {"content": "Contract terminates 60 days following written notice by either party."}
    ]
    answer = "Under the agreement, the contract terminates 60 days after written notice."

    assert grader.grade_support(answer, chunks) is True


def test_answer_support_offline_hallucinated() -> None:
    grader = AnswerSupportGrader(api_key=None)
    chunks = [
        {"content": "Contract terminates 60 days following written notice by either party."}
    ]
    answer = "All employees are entitled to forty days of paid personal vacation annually."

    assert grader.grade_support(answer, chunks) is False


def test_answer_support_mocked_llm() -> None:
    grader = AnswerSupportGrader(api_key="mock-key")
    chunks = [{"content": "Vendor invoices are paid via wire transfer."}]

    with patch.object(grader, "_call_llm") as mock_call:
        mock_call.return_value = "yes"
        assert grader.grade_support("Invoices paid via wire transfer", chunks) is True

        mock_call.return_value = "no"
        assert grader.grade_support("Invoices paid with bitcoin cryptocurrency", chunks) is False


def test_check_answer_support_node_grounded() -> None:
    initial_state: RagState = {
        "question": "What is the warranty period?",
        "tenant_id": "00000000-0000-0000-0000-000000000001",
        "retrieved_chunks": [
            {"content": "Seller provides a twelve-month warranty starting from delivery date."}
        ],
        "answer": "The warranty lasts twelve months from the delivery date.",
        "node_latencies": {},
    }

    new_state = check_answer_support_node(initial_state)

    assert new_state["grade"] == "supported"
    assert "check_answer_support_node" in new_state["node_latencies"]


def test_check_answer_support_node_hallucinated() -> None:
    initial_state: RagState = {
        "question": "What is the warranty period?",
        "tenant_id": "00000000-0000-0000-0000-000000000001",
        "retrieved_chunks": [
            {"content": "Seller provides a twelve-month warranty starting from delivery date."}
        ],
        "answer": "The warranty is unlimited lifetime coverage with free replacements forever.",
        "node_latencies": {},
    }

    new_state = check_answer_support_node(initial_state)

    assert new_state["grade"] == "unsupported"
    assert "check_answer_support_node" in new_state["node_latencies"]
