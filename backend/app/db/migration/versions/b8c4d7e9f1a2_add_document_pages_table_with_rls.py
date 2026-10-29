"""add_document_pages_table_with_rls

Revision ID: b8c4d7e9f1a2
Revises: 4923eb578c10
Create Date: 2026-10-29 19:25:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b8c4d7e9f1a2"
down_revision: str | None = "4923eb578c10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Creates document_pages table and enables Row Level Security (RLS)."""
    op.create_table(
        "document_pages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("page_no", sa.Integer(), nullable=False),
        sa.Column("image_storage_key", sa.String(length=1024), nullable=True),
        sa.Column("ocr_text", sa.Text(), nullable=True),
        sa.Column("layout_json", sa.JSON(), nullable=True),
        sa.Column("ocr_engine", sa.String(length=50), nullable=True),
        sa.Column(
            "used_vision_fallback",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "page_no", name="uq_document_page_number"),
    )

    op.create_index(
        op.f("ix_document_pages_tenant_id"), "document_pages", ["tenant_id"], unique=False
    )
    op.create_index(
        op.f("ix_document_pages_document_id"), "document_pages", ["document_id"], unique=False
    )

    # Enforce PostgreSQL Row Level Security (RLS) for tenant isolation
    op.execute("ALTER TABLE document_pages ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE document_pages FORCE ROW LEVEL SECURITY;")
    op.execute("""
        CREATE POLICY tenant_isolation_document_pages ON document_pages
        FOR ALL
        USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);
    """)


def downgrade() -> None:
    """Removes RLS policy and drops document_pages table."""
    op.execute("DROP POLICY IF EXISTS tenant_isolation_document_pages ON document_pages;")
    op.drop_index(op.f("ix_document_pages_document_id"), table_name="document_pages")
    op.drop_index(op.f("ix_document_pages_tenant_id"), table_name="document_pages")
    op.drop_table("document_pages")
