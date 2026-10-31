import enum

from pydantic import BaseModel, ConfigDict, Field


class DocumentType(enum.StrEnum):
    INVOICE = "invoice"
    CONTRACT = "contract"
    OTHER = "other"


class ExtractedField[T](BaseModel):
    """Represents an extracted field accompanied by confidence and source provenance."""

    model_config = ConfigDict(from_attributes=True)

    value: T | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    page_no: int | None = Field(default=None, ge=1)
    bbox: list[float] | None = None  # Normalized [x0, y0, x1, y1] coordinates (0.0 to 1.0)


class DocumentClassification(BaseModel):
    """Classification of an uploaded document's type."""

    doc_type: DocumentType = DocumentType.OTHER
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reasoning: str = ""


class InvoiceLineItem(BaseModel):
    """A single line item from an invoice table."""

    description: str | None = None
    quantity: float | None = None
    unit_price: float | None = None
    amount: float | None = None
    page_no: int | None = None


class InvoiceExtraction(BaseModel):
    """Structured extraction schema for commercial invoices and receipts."""

    model_config = ConfigDict(from_attributes=True)

    vendor_name: ExtractedField[str] = Field(default_factory=ExtractedField[str])
    vendor_address: ExtractedField[str] = Field(default_factory=ExtractedField[str])
    customer_name: ExtractedField[str] = Field(default_factory=ExtractedField[str])
    invoice_number: ExtractedField[str] = Field(default_factory=ExtractedField[str])
    invoice_date: ExtractedField[str] = Field(default_factory=ExtractedField[str])  # YYYY-MM-DD
    due_date: ExtractedField[str] = Field(default_factory=ExtractedField[str])  # YYYY-MM-DD
    currency: ExtractedField[str] = Field(default_factory=lambda: ExtractedField[str](value="USD"))
    subtotal: ExtractedField[float] = Field(default_factory=ExtractedField[float])
    tax_amount: ExtractedField[float] = Field(default_factory=ExtractedField[float])
    total_amount: ExtractedField[float] = Field(default_factory=ExtractedField[float])
    line_items: list[InvoiceLineItem] = Field(default_factory=list)


class ContractExtraction(BaseModel):
    """Structured extraction schema for legal contracts and agreements."""

    model_config = ConfigDict(from_attributes=True)

    title: ExtractedField[str] = Field(default_factory=ExtractedField[str])
    parties: list[str] = Field(default_factory=list)
    effective_date: ExtractedField[str] = Field(default_factory=ExtractedField[str])  # YYYY-MM-DD
    expiration_date: ExtractedField[str] = Field(default_factory=ExtractedField[str])  # YYYY-MM-DD
    term_length: ExtractedField[str] = Field(default_factory=ExtractedField[str])
    renewal_terms: ExtractedField[str] = Field(default_factory=ExtractedField[str])
    payment_terms: ExtractedField[str] = Field(default_factory=ExtractedField[str])
    termination_clause: ExtractedField[str] = Field(default_factory=ExtractedField[str])
    governing_law: ExtractedField[str] = Field(default_factory=ExtractedField[str])
