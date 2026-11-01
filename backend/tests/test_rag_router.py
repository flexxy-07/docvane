from backend.app.services.rag.nodes.router import QueryRouter, router_node
from backend.app.services.rag.state import RagState


def test_router_20_hand_made_questions() -> None:
    router = QueryRouter()

    test_cases: list[tuple[str, str]] = [
        # --- Direct ---
        ("Hello there!", "direct"),
        ("Hi, how are you today?", "direct"),
        ("Who are you and what can you do?", "direct"),
        ("Thank you very much for your help", "direct"),

        # --- Pure SQL ---
        ("What is the total amount invoiced across all vendors in 2024?", "sql"),
        ("How many invoices were uploaded last month?", "sql"),
        ("What is the average total cost of contracts?", "sql"),
        ("Count all invoices for Acme Corp", "sql"),

        # --- Both (SQL + Document Qualitative) ---
        ("What is the total amount invoiced by Acme and what do their payment terms say?", "both"),
        ("How many contracts have expired and summarize the termination clauses?", "both"),
        ("Give me the total spent on Globex and explain their governing law", "both"),
        ("What is the sum of tax paid and explain our liability obligations?", "both"),

        # --- Transform (Complex, Broad, Multi-faceted) ---
        ("Compare and contrast the liability clauses between Acme and Globex", "transform"),
        (
            "What happens if a delivery is delayed by more than 30 days under all agreements?",
            "transform",
        ),
        ("Give me a comprehensive overview of our potential risks and obligations", "transform"),
        ("What are the pros and cons of the renewal terms across agreements?", "transform"),

        # --- Simple (Direct Fact/Clause Lookups) ---
        ("What is the invoice number on the Acme PDF?", "simple"),
        ("When was this contract signed?", "simple"),
        ("Who is the primary contact listed on page 3?", "simple"),
        ("What is the due date for invoice INV-1002?", "simple"),
    ]

    assert len(test_cases) == 20

    for question, expected_route in test_cases:
        actual_route = router.classify(question)
        assert actual_route == expected_route, (
            f"Question: '{question}' expected '{expected_route}', got '{actual_route}'"
        )


def test_router_node_execution() -> None:
    initial_state: RagState = {
        "question": "What is the total amount paid to Acme Corp in 2024?",
        "tenant_id": "00000000-0000-0000-0000-000000000001",
        "node_latencies": {},
    }

    new_state = router_node(initial_state)

    assert new_state["route"] == "sql"
    assert "router_node" in new_state["node_latencies"]
    assert new_state["node_latencies"]["router_node"] >= 0.0
