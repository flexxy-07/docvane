import enum
import uuid

from sqlalchemy import (
    JSON,
    Boolean,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class FieldStatus(enum.StrEnum):
    AUTO = "auto"
    NEEDS_REVIEW = "needs_review"
    CORRECTED = "corrected"


class DocumentStatus(enum.StrEnum):
    UPLOADED = "uploaded"
    QUEUED = "queued"
    PARSING = "parsing"
    EXTRACTING = "extracting"
    NEEDS_REVIEW = "needs_review"
    REVIEWED = "reviewed"
    INDEXING = "indexing"
    READY = "ready"
    FAILED = "failed"


class UserRole(enum.StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


class Tenant(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    memberships: Mapped[list["Membership"]] = relationship(
        "Membership", back_populates="tenant", cascade="all, delete-orphan"
    )
    documents: Mapped[list["Document"]] = relationship(
        "Document", back_populates="tenant", cascade="all, delete-orphan"
    )


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    memberships: Mapped[list["Membership"]] = relationship(
        "Membership", back_populates="user", cascade="all, delete-orphan"
    )


class Membership(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("user_id", "tenant_id", name="uq_membership_user_tenant"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", native_enum=False), default=UserRole.MEMBER, nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="memberships")
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="memberships")


class Document(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "documents"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)
    doc_type: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # invoice, contract, etc.
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, name="document_status", native_enum=False),
        default=DocumentStatus.UPLOADED,
        index=True,
        nullable=False,
    )
    storage_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), index=True, nullable=False)  # SHA-256
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="documents")

    pages: Mapped[list["DocumentPage"]] = relationship(
        "DocumentPage", back_populates="document", cascade="all, delete-orphan"
    )

class DocumentPage(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "document_pages"
    __table_args__ = (
        UniqueConstraint("document_id", "page_no", name="uq_document_page_number"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), index=True, nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    page_no: Mapped[int] = mapped_column(Integer, nullable=False)
    image_storage_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    ocr_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    layout_json: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    ocr_engine: Mapped[str | None] = mapped_column(String(50), nullable=True)
    used_vision_fallback: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant")
    document: Mapped["Document"] = relationship("Document", back_populates="pages")


class ExtractedFieldModel(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "extracted_fields"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    field_name: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    field_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    source_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bbox: Mapped[list[float] | None] = mapped_column(JSON, nullable=True)
    status: Mapped[FieldStatus] = mapped_column(
        Enum(FieldStatus, name="field_status", native_enum=False),
        default=FieldStatus.AUTO,
        index=True,
        nullable=False,
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant")
    document: Mapped["Document"] = relationship("Document")


class Invoice(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "invoices"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    vendor_name: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    customer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    invoice_number: Mapped[str | None] = mapped_column(String(100), index=True, nullable=True)
    invoice_date: Mapped[str | None] = mapped_column(String(50), nullable=True)
    due_date: Mapped[str | None] = mapped_column(String(50), nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="USD", nullable=False)
    subtotal: Mapped[float | None] = mapped_column(Float, nullable=True)
    tax_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_amount: Mapped[float | None] = mapped_column(Float, index=True, nullable=True)
    line_items: Mapped[list[dict[str, object]] | None] = mapped_column(JSON, nullable=True)

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant")
    document: Mapped["Document"] = relationship("Document")


class Contract(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "contracts"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    parties: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    effective_date: Mapped[str | None] = mapped_column(String(50), nullable=True)
    expiration_date: Mapped[str | None] = mapped_column(String(50), nullable=True)
    term_length: Mapped[str | None] = mapped_column(String(100), nullable=True)
    governing_law: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant")
    document: Mapped["Document"] = relationship("Document")


