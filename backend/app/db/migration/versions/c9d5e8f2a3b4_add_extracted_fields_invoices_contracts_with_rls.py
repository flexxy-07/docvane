"""add_extracted_fields_invoices_contracts_with_rls

Revision ID: c9d5e8f2a3b4
Revises: b8c4d7e9f1a2
Create Date: 2026-10-31 13:20:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c9d5e8f2a3b4"
down_revision: str | None = "b8c4d7e9f1a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Creates extracted_fields, invoices, and contracts tables with Row Level Security (RLS)."""

    # 1. extracted_fields table
    op.create_table(
        "extracted_fields",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("field_name", sa.String(length=100), nullable=False),
        sa.Column("field_value", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("source_page", sa.Integer(), nullable=True),
        sa.Column("bbox", sa.JSON(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("AUTO", "NEEDS_REVIEW", "CORRECTED", name="field_status", native_enum=False),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_extracted_fields_tenant_id"), "extracted_fields", ["tenant_id"], unique=False
    )
    op.create_index(
        op.f("ix_extracted_fields_document_id"), "extracted_fields", ["document_id"], unique=False
    )
    op.create_index(
        op.f("ix_extracted_fields_field_name"), "extracted_fields", ["field_name"], unique=False
    )
    op.create_index(
        op.f("ix_extracted_fields_status"), "extracted_fields", ["status"], unique=False
    )

    # 2. invoices table
    op.create_table(
        "invoices",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("vendor_name", sa.String(length=255), nullable=True),
        sa.Column("customer_name", sa.String(length=255), nullable=True),
        sa.Column("invoice_number", sa.String(length=100), nullable=True),
        sa.Column("invoice_date", sa.String(length=50), nullable=True),
        sa.Column("due_date", sa.String(length=50), nullable=True),
        sa.Column("currency", sa.String(length=10), nullable=False, server_default="USD"),
        sa.Column("subtotal", sa.Float(), nullable=True),
        sa.Column("tax_amount", sa.Float(), nullable=True),
        sa.Column("total_amount", sa.Float(), nullable=True),
        sa.Column("line_items", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", name="uq_invoices_document_id"),
    )
    op.create_index(op.f("ix_invoices_tenant_id"), "invoices", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_invoices_vendor_name"), "invoices", ["vendor_name"], unique=False)
    op.create_index(
        op.f("ix_invoices_invoice_number"), "invoices", ["invoice_number"], unique=False
    )
    op.create_index(op.f("ix_invoices_total_amount"), "invoices", ["total_amount"], unique=False)

    # 3. contracts table
    op.create_table(
        "contracts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("parties", sa.JSON(), nullable=True),
        sa.Column("effective_date", sa.String(length=50), nullable=True),
        sa.Column("expiration_date", sa.String(length=50), nullable=True),
        sa.Column("term_length", sa.String(length=100), nullable=True),
        sa.Column("governing_law", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", name="uq_contracts_document_id"),
    )
    op.create_index(op.f("ix_contracts_tenant_id"), "contracts", ["tenant_id"], unique=False)

    # 4. Enforce PostgreSQL Row Level Security (RLS) on all 3 tables
    for table in ["extracted_fields", "invoices", "contracts"]:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")
        op.execute(f"""
            CREATE POLICY tenant_isolation_{table} ON {table}
            FOR ALL
            USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);
        """)


def downgrade() -> None:
    """Removes RLS policies and drops tables."""
    for table in ["contracts", "invoices", "extracted_fields"]:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{table} ON {table};")

    op.drop_table("contracts")
    op.drop_table("invoices")
    op.drop_table("extracted_fields")
