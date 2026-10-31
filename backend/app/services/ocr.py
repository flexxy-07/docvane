import base64
import json
import logging
from dataclasses import dataclass
from typing import Any, cast

from litellm import completion
from litellm.types.utils import ModelResponse

from backend.app.core.config import settings

logger = logging.getLogger(__name__)

# System prompt directing the Vision LLM to extract OCR text, layout blocks, and structured tables
VISION_OCR_SYSTEM_PROMPT = """You are a high-accuracy Document OCR and Layout Analysis engine.
Analyze the provided document page image and output a clean JSON object with the following schema:
{
  "text": "Full extracted verbatim text in natural reading order. "
          "Format any table as a Markdown table (| Col 1 | Col 2 |)",
  "blocks": [
    {
      "type": "header" | "paragraph" | "table" | "key_value",
      "text": "Content of this block. If table, format as complete Markdown table.",
      "confidence": float between 0.0 and 1.0,
      "table_data": {
        "headers": ["Col 1", "Col 2"],
        "rows": [["Val 1", "Val 2"]]
      }
    }
  ],
  "confidence": float overall confidence between 0.0 and 1.0
}
Rules:
1. For "table" blocks, include both Markdown in "text" AND "table_data" with headers and rows.
2. For non-table blocks, "table_data" can be null or omitted.
3. Preserve all row items, quantities, currency symbols, and totals verbatim.
4. Respond ONLY with valid JSON. Do not wrap in markdown quotes if possible.
"""


@dataclass
class OCRPageResult:
    """Represents the parsed OCR output for a single page."""

    text: str
    layout_json: dict[str, Any] | None
    engine: str
    used_vision_fallback: bool
    confidence: float


class OCRService:
    """
    Hybrid OCR & Layout service:
    1. Fast-path: Uses native digital text if already present in the PDF (0 cost, instant).
    2. Fallback: If scanned/image or low text density, routes to Vision LLM.
    """

    def __init__(self, model_name: str | None = None) -> None:
        self.model = model_name or settings.DEFAULT_LLM_MODEL
        self.api_key = settings.GEMINI_API_KEY

    def is_text_sufficient(self, text: str | None, min_chars: int = 50) -> bool:
        """Determines if the directly extracted PDF text is adequate or if it's a scan."""
        if not text:
            return False
        clean = text.strip()
        return len(clean) >= min_chars

    def extract_native_tables(self, page_bytes: bytes) -> tuple[str | None, list[dict[str, Any]]]:
        """
        Uses pdfplumber to detect and extract tabular grids from digital PDFs.
        Returns a tuple of (combined_markdown_tables, list_of_table_block_dicts).
        """
        try:
            import io

            import pdfplumber

            table_blocks: list[dict[str, Any]] = []
            markdown_tables: list[str] = []

            with pdfplumber.open(io.BytesIO(page_bytes)) as pdf:
                if not pdf.pages:
                    return None, []
                first_page = pdf.pages[0]
                extracted_tables = first_page.extract_tables()

                for tbl in extracted_tables:
                    # Filter out empty or single-cell non-tables
                    if not tbl or len(tbl) < 2:
                        continue
                    headers = [str(c or "").strip() for c in tbl[0]]
                    rows = [[str(c or "").strip() for c in row] for row in tbl[1:]]

                    # Build markdown table representation
                    header_line = "| " + " | ".join(headers) + " |"
                    sep_line = "| " + " | ".join(["---"] * len(headers)) + " |"
                    row_lines = ["| " + " | ".join(r) + " |" for r in rows]
                    md = "\n".join([header_line, sep_line, *row_lines])

                    markdown_tables.append(md)
                    table_blocks.append({
                        "type": "table",
                        "text": md,
                        "confidence": 1.0,
                        "table_data": {"headers": headers, "rows": rows},
                    })

            if markdown_tables:
                return "\n\n".join(markdown_tables), table_blocks
            return None, []
        except Exception as e:
            logger.warning(
                "pdfplumber table extraction failed, falling back to direct text",
                extra={"error": str(e)},
            )
            return None, []

    def parse_page(
        self,
        page_bytes: bytes,
        mime_type: str = "application/pdf",
        existing_text: str | None = None,
    ) -> OCRPageResult:
        """
        Parses a single page. If existing_text has sufficient content, uses it
        while preserving any tables detected via pdfplumber.
        Otherwise triggers vision LLM fallback.
        """
        # 1. Fast-path: Native text is sufficient
        if self.is_text_sufficient(existing_text):
            final_text = existing_text.strip() if existing_text else ""
            table_blocks: list[dict[str, Any]] = []

            # Check if digital PDF contains extractable table grids
            if mime_type == "application/pdf":
                table_md, table_blocks = self.extract_native_tables(page_bytes)
                if table_md:
                    # Append structured markdown table to the text so LLMs & chunkers get both
                    final_text = f"{final_text}\n\n### Extracted Tables\n{table_md}"

            return OCRPageResult(
                text=final_text,
                layout_json={"source": "native_pdf", "blocks": table_blocks},
                engine="pdfplumber" if table_blocks else "pypdf",
                used_vision_fallback=False,
                confidence=1.0,
            )

        # 2. Vision LLM Fallback (for scanned PDFs or raw images)
        return self._extract_with_vision(page_bytes, mime_type)

    def _extract_with_vision(self, file_bytes: bytes, mime_type: str) -> OCRPageResult:
        """Calls Vision LLM via LiteLLM to extract text and layout blocks."""
        b64_data = base64.b64encode(file_bytes).decode("utf-8")
        data_url = f"data:{mime_type};base64,{b64_data}"

        messages = [
            {"role": "system", "content": VISION_OCR_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Extract all text and layout structure from this page.",
                    },
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            },
        ]

        try:
            resp = completion(
                model=self.model,
                messages=messages,
                api_key=self.api_key if self.api_key else None,
                temperature=0.0,
            )
            response = cast(ModelResponse, resp)
            raw_content = response.choices[0].message.content or ""
            clean_json = self._clean_json_response(raw_content)
            parsed: dict[str, Any] = json.loads(clean_json)

            return OCRPageResult(
                text=parsed.get("text", "").strip(),
                layout_json=parsed,
                engine=f"vision:{self.model}",
                used_vision_fallback=True,
                confidence=float(parsed.get("confidence", 0.9)),
            )

        except Exception as e:
            logger.error(
                "Vision OCR extraction failed",
                extra={"error": str(e), "model": self.model},
            )
            # Graceful degrade: return whatever we can or empty result with low confidence
            return OCRPageResult(
                text="",
                layout_json={"error": str(e)},
                engine=f"vision_failed:{self.model}",
                used_vision_fallback=True,
                confidence=0.0,
            )

    def _clean_json_response(self, content: str) -> str:
        """Strips markdown code fence wrappers from LLM responses if present."""
        clean = content.strip()
        if clean.startswith("```json"):
            clean = clean[7:]
        elif clean.startswith("```"):
            clean = clean[3:]
        if clean.endswith("```"):
            clean = clean[:-3]
        return clean.strip()
