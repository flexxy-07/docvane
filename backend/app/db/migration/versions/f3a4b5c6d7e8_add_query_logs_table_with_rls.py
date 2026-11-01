"""add_query_logs_table_with_rls

Revision ID: f3a4b5c6d7e8
Revises: e2f3a4b5c6d7
Create Date: 2026-11-01 10:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f3a4b5c6d7e8"
down_revision: str | None = "e2f3a4b5c6d7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Creates query_logs table with indexes and tenant Row-Level Security."""
    op.create_table(
        "query_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("strategy", sa.String(length=50), nullable=False),
        sa.Column("route", sa.String(length=50), nullable=False, server_default="rag"),
        sa.Column("filters", sa.JSON(), nullable=True),
        sa.Column("retrieved_chunk_ids", sa.JSON(), nullable=True),
        sa.Column("top_score", sa.Float(), nullable=True),
        sa.Column("latency_ms", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("token_count", sa.Integer(), nullable=True),
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
            ["tenant_id"],
            ["tenants.id"],
            name="fk_query_logs_tenant_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_query_logs"),
    )

    op.create_index(
        "ix_query_logs_tenant_id",
        "query_logs",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        "ix_query_logs_tenant_created",
        "query_logs",
        ["tenant_id", "created_at"],
        unique=False,
    )

    # Enable and force PostgreSQL Row Level Security (RLS)
    op.execute("ALTER TABLE query_logs ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE query_logs FORCE ROW LEVEL SECURITY;")

    # Multi-tenant isolation policy
    op.execute(
        """
        CREATE POLICY tenant_isolation_policy ON query_logs
        FOR ALL
        USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);
        """
    )


def downgrade() -> None:
    """Removes query_logs table and associated security policies."""
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON query_logs;")
    op.drop_index("ix_query_logs_tenant_created", table_name="query_logs")
    op.drop_index("ix_query_logs_tenant_id", table_name="query_logs")
    op.drop_table("query_logs")
