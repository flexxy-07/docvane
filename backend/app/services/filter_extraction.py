import re
from dataclasses import dataclass
from typing import Any

from backend.app.services.retrieval import RetrievalFilter


@dataclass
class ExtractedFilters:
    """Structured extraction of filters and cleaned query from natural text."""

    filters: RetrievalFilter
    doc_type: str | None = None
    vendor_name: str | None = None
    year: int | None = None
    page_number: int | None = None
    cleaned_query: str = ""
    extracted_metadata: dict[str, Any] | None = None


class QueryFilterExtractor:
    """
    Extracts semantic metadata filters (doc type, vendor, year, page number, tables)
    from natural language user queries and strips filter cues to produce clean search text.
    """

    def extract(self, query: str) -> ExtractedFilters:
        clean_text = query.strip()
        doc_type: str | None = None
        vendor_name: str | None = None
        year: int | None = None
        page_number: int | None = None
        chunk_types: list[str] | None = None
        metadata: dict[str, Any] = {}

        # 1. Detect Document Types
        if re.search(
            r"\b(invoice|invoices|bill|bills|receipt|receipts)\b",
            clean_text,
            re.IGNORECASE,
        ):
            doc_type = "invoice"
            metadata["doc_type"] = "invoice"
        elif re.search(
            r"\b(contract|contracts|agreement|agreements|nda|terms of service)\b",
            clean_text,
            re.IGNORECASE,
        ):
            doc_type = "contract"
            metadata["doc_type"] = "contract"

        # 2. Detect 4-digit Year
        year_match = re.search(r"\b(19\d\d|20\d\d)\b", clean_text)
        if year_match:
            year = int(year_match.group(1))
            metadata["year"] = year

        # 3. Detect Page Number (e.g. "page 2", "p. 3")
        page_match = re.search(r"\b(?:page|p\.?)\s*(\d+)\b", clean_text, re.IGNORECASE)
        if page_match:
            page_number = int(page_match.group(1))

        # 4. Detect Table / Tabular requirements
        if re.search(
            r"\b(table|tabular|line items?|breakdown|itemized)\b",
            clean_text,
            re.IGNORECASE,
        ):
            chunk_types = ["table"]

        # 5. Detect Vendor / Entity cues (e.g. "with Globex", "in the Acme invoice")
        vendor_match = re.search(
            r"\b(?:with|from\s+the|from|by\s+the|by|vendor|for)\s+([A-Z][A-Za-z0-9&.\s]{1,30}?)(?=\s+(?:in|dated|on|from|contract|invoice|agreement)|\?|$|,|\.)",
            clean_text,
        )
        if not vendor_match:
            vendor_match = re.search(
                r"\b(?:in\s+the|in)\s+([A-Z][A-Za-z0-9&.\s]{1,30}?)(?=\s+(?:contract|invoice|agreement|receipt|bill))",
                clean_text,
            )

        if vendor_match:
            candidate = vendor_match.group(1).strip()
            # Exclude document types and common false positives
            doc_keywords = {
                "the", "a", "an", "page", "table", "invoice", "contract",
                "agreement", "nda", "receipt", "bill",
            }
            if not any(kw in candidate.lower().split() for kw in doc_keywords):
                vendor_name = candidate
                metadata["vendor_name"] = vendor_name

        # 6. Produce cleaned query by removing extracted cues
        cleaned = clean_text
        patterns_to_strip = [
            r"\b(?:page|p\.?)\s*\d+\b",
            r"\b(in\s+)?(19\d\d|20\d\d)\b",
            r"\b(?:in\s+the\s+|from\s+the\s+|in\s+|from\s+)?(?:invoice|contract|agreement|receipt|nda)s?\b",
            r"\b(?:with|from\s+the|from|in\s+the|in|by\s+the|by|vendor)\s+[A-Z][A-Za-z0-9&.\s]{1,30}?(?=\s|$|,|\.)",
        ]
        for pat in patterns_to_strip:
            cleaned = re.sub(pat, "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" ?,.")

        # Fallback to original text if stripped query becomes too short
        if len(cleaned) < 3:
            cleaned = clean_text

        retrieval_filter = RetrievalFilter(
            page_number=page_number,
            chunk_types=chunk_types,
            metadata_filters=metadata if metadata else None,
        )

        return ExtractedFilters(
            filters=retrieval_filter,
            doc_type=doc_type,
            vendor_name=vendor_name,
            year=year,
            page_number=page_number,
            cleaned_query=cleaned,
            extracted_metadata=metadata if metadata else None,
        )
