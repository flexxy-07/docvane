"""add_review_tasks_and_audit_logs_with_rls

Revision ID: d1e2f3a4b5c6
Revises: c9d5e8f2a3b4
Create Date: 2026-10-31 13:35:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d1e2f3a4b5c6"
down_revision: str | None = "c9d5e8f2a3b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Creates review_tasks and audit_logs tables with Row Level Security (RLS)."""

    # 1. review_tasks table
    op.create_table(
        "review_tasks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("field_id", sa.Uuid(), nullable=False),
        sa.Column("assigned_to_user_id", sa.Uuid(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING",
                "CLAIMED",
                "APPROVED",
                "CORRECTED",
                name="review_status",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("corrected_value", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["assigned_to_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["field_id"], ["extracted_fields.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_review_tasks_tenant_id"), "review_tasks", ["tenant_id"], unique=False
    )
    op.create_index(
        op.f("ix_review_tasks_document_id"), "review_tasks", ["document_id"], unique=False
    )
    op.create_index(
        op.f("ix_review_tasks_field_id"), "review_tasks", ["field_id"], unique=False
    )
    op.create_index(
        op.f("ix_review_tasks_assigned_to_user_id"),
        "review_tasks",
        ["assigned_to_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_review_tasks_status"), "review_tasks", ["status"], unique=False
    )

    # 2. audit_logs table
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("field_name", sa.String(length=100), nullable=True),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audit_logs_tenant_id"), "audit_logs", ["tenant_id"], unique=False)
    op.create_index(
        op.f("ix_audit_logs_document_id"), "audit_logs", ["document_id"], unique=False
    )
    op.create_index(op.f("ix_audit_logs_user_id"), "audit_logs", ["user_id"], unique=False)

    # 3. Enforce PostgreSQL Row Level Security (RLS) on both tables
    for table in ["review_tasks", "audit_logs"]:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")
        op.execute(f"""
            CREATE POLICY tenant_isolation_{table} ON {table}
            FOR ALL
            USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);
        """)


def downgrade() -> None:
    """Removes RLS policies and drops tables."""
    for table in ["audit_logs", "review_tasks"]:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{table} ON {table};")

    op.drop_table("audit_logs")
    op.drop_table("review_tasks")
