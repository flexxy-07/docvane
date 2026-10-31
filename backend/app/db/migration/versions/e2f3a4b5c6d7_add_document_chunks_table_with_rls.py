"""add_document_chunks_table_with_rls

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-10-31 17:55:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = "e2f3a4b5c6d7"
down_revision: str | None = "d1e2f3a4b5c6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Creates document_chunks table with HNSW vector index, full-text index, and RLS."""
    op.create_table(
        "document_chunks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("chunk_type", sa.String(length=50), nullable=False, server_default="text"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("embedding", Vector(768), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name="fk_document_chunks_document_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_document_chunks_tenant_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_document_chunks"),
    )

    op.create_index(
        "ix_document_chunks_tenant_id",
        "document_chunks",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        "ix_document_chunks_document_id",
        "document_chunks",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        "ix_document_chunks_tenant_doc_idx",
        "document_chunks",
        ["tenant_id", "document_id", "chunk_index"],
        unique=False,
    )

    # Vector cosine similarity HNSW index for semantic search
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_document_chunks_embedding
        ON document_chunks USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64);
        """
    )

    # GIN index for full-text search (BM25 / keyword search)
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_document_chunks_content_tsv
        ON document_chunks USING gin (to_tsvector('english', content));
        """
    )

    # Enable and force PostgreSQL Row Level Security (RLS)
    op.execute("ALTER TABLE document_chunks ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE document_chunks FORCE ROW LEVEL SECURITY;")

    # Multi-tenant isolation policy
    op.execute(
        """
        CREATE POLICY tenant_isolation_policy ON document_chunks
        FOR ALL
        USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);
        """
    )


def downgrade() -> None:
    """Removes document_chunks table and associated security policies."""
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON document_chunks;")
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding;")
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_content_tsv;")
    op.drop_index("ix_document_chunks_tenant_doc_idx", table_name="document_chunks")
    op.drop_index("ix_document_chunks_document_id", table_name="document_chunks")
    op.drop_index("ix_document_chunks_tenant_id", table_name="document_chunks")
    op.drop_table("document_chunks")
