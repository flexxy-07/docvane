import json
from unittest.mock import MagicMock, patch

from backend.app.services.ocr import OCRService


def test_is_text_sufficient() -> None:
    service = OCRService()

    # None or empty
    assert service.is_text_sufficient(None) is False
    assert service.is_text_sufficient("") is False
    assert service.is_text_sufficient("   \n\t  ") is False

    # Short string below min_chars (default 50)
    assert service.is_text_sufficient("Short text invoice #123") is False

    # Adequate text above min_chars
    long_text = "This is an invoice from Acme Corporation dated October 2026 for $1,250.00."
    assert service.is_text_sufficient(long_text) is True


def test_parse_page_fast_path_native_pdf() -> None:
    service = OCRService()
    sufficient_text = (
        "Standard invoice document with more than fifty characters of digital text content."
    )

    result = service.parse_page(
        page_bytes=b"dummy_pdf_bytes",
        mime_type="application/pdf",
        existing_text=sufficient_text,
    )

    assert result.used_vision_fallback is False
    assert result.engine == "pypdf"
    assert result.confidence == 1.0
    assert result.text == sufficient_text
    assert result.layout_json == {"source": "native_pdf", "blocks": []}


def test_parse_page_native_pdf_with_tables() -> None:
    service = OCRService()
    sufficient_text = "Invoice summary for services rendered in October 2026."

    mock_table_data = [
        ["Item Description", "Qty", "Price", "Total"],
        ["Cloud Server", "2", "$50.00", "$100.00"],
    ]

    mock_pdf = MagicMock()
    mock_page = MagicMock()
    mock_page.extract_tables.return_value = [mock_table_data]
    mock_pdf.pages = [mock_page]
    mock_pdf.__enter__.return_value = mock_pdf
    mock_pdf.__exit__.return_value = None

    with patch("pdfplumber.open", return_value=mock_pdf):
        result = service.parse_page(
            page_bytes=b"fake_pdf_data",
            mime_type="application/pdf",
            existing_text=sufficient_text,
        )

    assert result.engine == "pdfplumber"
    assert result.used_vision_fallback is False
    assert "| Item Description | Qty | Price | Total |" in result.text
    assert result.layout_json is not None
    assert len(result.layout_json["blocks"]) == 1
    table_block = result.layout_json["blocks"][0]
    assert table_block["type"] == "table"
    assert table_block["table_data"]["headers"] == ["Item Description", "Qty", "Price", "Total"]


def test_parse_page_vision_fallback_success() -> None:
    service = OCRService()
    mock_payload = {
        "text": "Invoice Header\n| Item | Amount |\n| --- | --- |\n| Widget | $500 |",
        "blocks": [
            {"type": "header", "text": "Invoice Header", "confidence": 0.98},
            {
                "type": "table",
                "text": "| Item | Amount |\n| --- | --- |\n| Widget | $500 |",
                "confidence": 0.95,
                "table_data": {
                    "headers": ["Item", "Amount"],
                    "rows": [["Widget", "$500"]],
                },
            },
        ],
        "confidence": 0.96,
    }

    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = f"```json\n{json.dumps(mock_payload)}\n```"
    mock_response.choices = [mock_choice]

    with patch("backend.app.services.ocr.completion", return_value=mock_response) as mock_llm:
        result = service.parse_page(
            page_bytes=b"scanned_image_bytes",
            mime_type="image/png",
            existing_text=None,
        )

        mock_llm.assert_called_once()
        assert result.used_vision_fallback is True
        assert "vision:" in result.engine
        assert result.confidence == 0.96
        assert "| Item | Amount |" in result.text
        assert result.layout_json == mock_payload


def test_parse_page_vision_fallback_error_handling() -> None:
    service = OCRService()

    with patch(
        "backend.app.services.ocr.completion",
        side_effect=RuntimeError("LiteLLM API Rate Limit"),
    ):
        result = service.parse_page(
            page_bytes=b"scanned_image_bytes",
            mime_type="image/png",
            existing_text=None,
        )

        assert result.used_vision_fallback is True
        assert "vision_failed:" in result.engine
        assert result.confidence == 0.0
        assert result.text == ""
        assert "LiteLLM API Rate Limit" in str(result.layout_json)
