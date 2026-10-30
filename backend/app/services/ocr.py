import base64
import json
import logging
from dataclasses import dataclass
from typing import Any, cast

from litellm import completion
from litellm.types.utils import ModelResponse

from backend.app.core.config import settings

logger = logging.getLogger(__name__)

# System prompt directing the Vision LLM to extract OCR text and layout blocks
VISION_OCR_SYSTEM_PROMPT = """You are a high-accuracy Document OCR and Layout Analysis engine.
Analyze the provided document page image and output a clean JSON object with the following schema:
{
  "text": "Full extracted verbatim text in natural reading order",
  "blocks": [
    {
      "type": "header" | "paragraph" | "table" | "key_value",
      "text": "Content of this block",
      "confidence": float between 0.0 and 1.0
    }
  ],
  "confidence": float overall confidence between 0.0 and 1.0
}
Respond ONLY with valid JSON. Do not wrap in markdown quotes if possible.
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

    def parse_page(
        self,
        page_bytes: bytes,
        mime_type: str = "application/pdf",
        existing_text: str | None = None,
    ) -> OCRPageResult:
        """
        Parses a single page. If existing_text has sufficient content, uses it.
        Otherwise triggers vision LLM fallback.
        """
        # 1. Fast-path: Native text is sufficient
        if self.is_text_sufficient(existing_text):
            return OCRPageResult(
                text=existing_text.strip(),  # type: ignore[union-attr]
                layout_json={"source": "native_pdf", "blocks": []},
                engine="pypdf",
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
