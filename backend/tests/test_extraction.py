import json
from unittest.mock import MagicMock, patch

from backend.app.schemas.extraction import DocumentType, ExtractedField, InvoiceExtraction
from backend.app.services.extraction import ExtractionService


def test_classify_document_empty() -> None:
    service = ExtractionService()
    result = service.classify_document("")
    assert result.doc_type == DocumentType.OTHER
    assert result.confidence == 0.0


def test_classify_document_success() -> None:
    service = ExtractionService()
    mock_payload = {
        "doc_type": "invoice",
        "confidence": 0.98,
        "reasoning": "Contains billing terms and line items",
    }
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = json.dumps(mock_payload)
    mock_response.choices = [mock_choice]

    with patch("backend.app.services.extraction.completion", return_value=mock_response):
        result = service.classify_document("INVOICE #INV-2026-001\nVendor: Acme Corp\nTotal: $500")

    assert result.doc_type == DocumentType.INVOICE
    assert result.confidence == 0.98
    assert "billing" in result.reasoning


def test_extract_invoice_success_and_arithmetic_boost() -> None:
    service = ExtractionService()
    mock_payload = {
        "vendor_name": {"value": "Acme Corp", "confidence": 0.95, "page_no": 1},
        "invoice_number": {"value": "INV-101", "confidence": 0.95, "page_no": 1},
        "currency": {"value": "USD", "confidence": 0.95, "page_no": 1},
        "subtotal": {"value": 100.0, "confidence": 0.90, "page_no": 1},
        "tax_amount": {"value": 10.0, "confidence": 0.90, "page_no": 1},
        "total_amount": {"value": 110.0, "confidence": 0.85, "page_no": 1},
        "line_items": [
            {"description": "Service fee", "quantity": 1, "unit_price": 100.0, "amount": 100.0}
        ],
    }
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = f"```json\n{json.dumps(mock_payload)}\n```"
    mock_response.choices = [mock_choice]

    with patch("backend.app.services.extraction.completion", return_value=mock_response):
        invoice = service.extract_invoice("Invoice text content")

    assert invoice.vendor_name.value == "Acme Corp"
    assert invoice.total_amount.value == 110.0
    # Mathematical consistency (100 + 10 == 110) should boost confidence (0.85 + 0.10 = 0.95)
    assert invoice.total_amount.confidence == 0.95


def test_validate_invoice_confidence_mismatch_penalty() -> None:
    service = ExtractionService()
    invoice = InvoiceExtraction(
        subtotal=ExtractedField[float](value=100.0, confidence=0.90),
        tax_amount=ExtractedField[float](value=10.0, confidence=0.90),
        total_amount=ExtractedField[float](value=150.0, confidence=0.85),  # 100 + 10 != 150
    )

    validated = service.validate_invoice_confidence(invoice)
    # Math mismatch should penalize total confidence
    assert validated.total_amount.confidence == 0.55


def test_extract_contract_success() -> None:
    service = ExtractionService()
    mock_payload = {
        "title": {"value": "Non-Disclosure Agreement", "confidence": 0.95, "page_no": 1},
        "parties": ["Acme Corp", "Beta LLC"],
        "effective_date": {"value": "2026-01-01", "confidence": 0.90, "page_no": 1},
        "governing_law": {"value": "Delaware", "confidence": 0.92, "page_no": 2},
    }
    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = json.dumps(mock_payload)
    mock_response.choices = [mock_choice]

    with patch("backend.app.services.extraction.completion", return_value=mock_response):
        contract = service.extract_contract("NDA between Acme Corp and Beta LLC")

    assert contract.title.value == "Non-Disclosure Agreement"
    assert "Beta LLC" in contract.parties
    assert contract.governing_law.value == "Delaware"
