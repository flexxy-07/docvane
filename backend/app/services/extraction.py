import json
import logging
from typing import cast

from litellm import completion
from litellm.types.utils import ModelResponse

from backend.app.core.config import settings
from backend.app.schemas.extraction import (
    ContractExtraction,
    DocumentClassification,
    DocumentType,
    InvoiceExtraction,
)

logger = logging.getLogger(__name__)

CLASSIFIER_SYSTEM_PROMPT = """You are an expert Document Classifier.
Analyze the following document text and classify it into one of these exact types:
- "invoice": Commercial bills, receipts, utility bills, billing statements.
- "contract": Legal agreements, master services agreements, NDAs, leases, employment contracts.
- "other": Reports, letters, articles, general notes.

Return ONLY a valid JSON object with the schema:
{
  "doc_type": "invoice" | "contract" | "other",
  "confidence": float between 0.0 and 1.0,
  "reasoning": "Short 1-sentence justification"
}
"""

INVOICE_EXTRACTION_SYSTEM_PROMPT = """You are a precision financial extraction engine.
Analyze the provided document text and extract structured fields conforming to this JSON schema:
{
  "vendor_name": {"value": str | null, "confidence": float, "page_no": int | null},
  "vendor_address": {"value": str | null, "confidence": float, "page_no": int | null},
  "customer_name": {"value": str | null, "confidence": float, "page_no": int | null},
  "invoice_number": {"value": str | null, "confidence": float, "page_no": int | null},
  "invoice_date": {"value": "YYYY-MM-DD" | null, "confidence": float, "page_no": int | null},
  "due_date": {"value": "YYYY-MM-DD" | null, "confidence": float, "page_no": int | null},
  "currency": {"value": "USD" | "EUR" | "GBP" | str, "confidence": float, "page_no": int | null},
  "subtotal": {"value": float | null, "confidence": float, "page_no": int | null},
  "tax_amount": {"value": float | null, "confidence": float, "page_no": int | null},
  "total_amount": {"value": float | null, "confidence": float, "page_no": int | null},
  "line_items": [
    {
      "description": str | null,
      "quantity": float | null,
      "unit_price": float | null,
      "amount": float | null,
      "page_no": int | null
    }
  ]
}
Confidence rules:
- Assign 0.95+ only when the value is explicitly stated and unambiguous.
- If inferred or blurry, assign between 0.5 and 0.8.
- If a field is not found, set "value" to null and "confidence" to 0.0.
Respond ONLY with valid JSON.
"""

CONTRACT_EXTRACTION_SYSTEM_PROMPT = """You are a precision legal contract analysis engine.
Analyze the provided document text and extract structured fields conforming to this JSON schema:
{
  "title": {"value": str | null, "confidence": float, "page_no": int | null},
  "parties": [str],
  "effective_date": {"value": "YYYY-MM-DD" | null, "confidence": float, "page_no": int | null},
  "expiration_date": {"value": "YYYY-MM-DD" | null, "confidence": float, "page_no": int | null},
  "term_length": {"value": str | null, "confidence": float, "page_no": int | null},
  "renewal_terms": {"value": str | null, "confidence": float, "page_no": int | null},
  "payment_terms": {"value": str | null, "confidence": float, "page_no": int | null},
  "termination_clause": {"value": str | null, "confidence": float, "page_no": int | null},
  "governing_law": {"value": str | null, "confidence": float, "page_no": int | null}
}
Respond ONLY with valid JSON.
"""


class ExtractionService:
    """Manages document classification, field extraction, and confidence scoring."""

    def __init__(self, model_name: str | None = None) -> None:
        self.model = model_name or settings.DEFAULT_LLM_MODEL
        self.api_key = settings.GEMINI_API_KEY

    def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        """Helper to invoke LiteLLM and return text content."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        resp = completion(
            model=self.model,
            messages=messages,
            api_key=self.api_key if self.api_key else None,
            temperature=0.0,
        )
        response = cast(ModelResponse, resp)
        return response.choices[0].message.content or ""

    def _clean_json(self, content: str) -> str:
        clean = content.strip()
        if clean.startswith("```json"):
            clean = clean[7:]
        elif clean.startswith("```"):
            clean = clean[3:]
        if clean.endswith("```"):
            clean = clean[:-3]
        return clean.strip()

    def classify_document(self, document_text: str) -> DocumentClassification:
        """Classifies document into 'invoice', 'contract', or 'other'."""
        if not document_text.strip():
            return DocumentClassification(
                doc_type=DocumentType.OTHER,
                confidence=0.0,
                reasoning="Empty document text",
            )

        # Truncate preview text for classifier efficiency (first 3000 chars is plenty)
        preview = document_text[:3000]
        user_prompt = f"Classify this document based on the following text:\n\n{preview}"

        try:
            raw = self._call_llm(CLASSIFIER_SYSTEM_PROMPT, user_prompt)
            clean = self._clean_json(raw)
            data = json.loads(clean)
            return DocumentClassification(**data)
        except Exception as e:
            logger.error("Document classification failed", extra={"error": str(e)})
            return DocumentClassification(
                doc_type=DocumentType.OTHER,
                confidence=0.0,
                reasoning=f"Classification error: {e}",
            )

    def extract_invoice(self, document_text: str) -> InvoiceExtraction:
        """Extracts structured invoice fields and applies mathematical confidence validation."""
        user_prompt = f"Extract all invoice data from the following text:\n\n{document_text}"

        try:
            raw = self._call_llm(INVOICE_EXTRACTION_SYSTEM_PROMPT, user_prompt)
            clean = self._clean_json(raw)
            data = json.loads(clean)
            extraction = InvoiceExtraction(**data)
            return self.validate_invoice_confidence(extraction)
        except Exception as e:
            logger.error("Invoice extraction failed", extra={"error": str(e)})
            return InvoiceExtraction()

    def extract_contract(self, document_text: str) -> ContractExtraction:
        """Extracts structured legal contract fields."""
        user_prompt = f"Extract all contract terms from the following text:\n\n{document_text}"

        try:
            raw = self._call_llm(CONTRACT_EXTRACTION_SYSTEM_PROMPT, user_prompt)
            clean = self._clean_json(raw)
            data = json.loads(clean)
            return ContractExtraction(**data)
        except Exception as e:
            logger.error("Contract extraction failed", extra={"error": str(e)})
            return ContractExtraction()

    def validate_invoice_confidence(self, invoice: InvoiceExtraction) -> InvoiceExtraction:
        """
        Calculates and boosts/penalizes confidence based on mathematical consistency:
        - If subtotal + tax_amount == total_amount, boost confidence.
        - If math contradicts, penalize total confidence.
        """
        sub = invoice.subtotal.value
        tax = invoice.tax_amount.value
        tot = invoice.total_amount.value

        if sub is not None and tax is not None and tot is not None:
            expected_total = round(sub + tax, 2)
            actual_total = round(tot, 2)

            if abs(expected_total - actual_total) <= 0.02:  # Tolerance for minor rounding
                # Arithmetic verified: boost confidence
                invoice.total_amount.confidence = min(1.0, invoice.total_amount.confidence + 0.1)
                invoice.subtotal.confidence = min(1.0, invoice.subtotal.confidence + 0.05)
            else:
                # Arithmetic mismatch: penalize confidence so it routes to review queue
                logger.warning(
                    "Invoice arithmetic mismatch",
                    extra={"expected": expected_total, "actual": actual_total},
                )
                invoice.total_amount.confidence = max(0.1, invoice.total_amount.confidence - 0.3)

        return invoice
