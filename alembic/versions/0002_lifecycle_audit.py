"""Lifecycle audit ledger for data-lifecycle events.

Revision ID: 0002_lifecycle_audit
Revises: 0001_baseline
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0002_lifecycle_audit"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lifecycle_audit",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("entity", sa.String(), nullable=True),
        sa.Column("revision", sa.String(), nullable=True),
        sa.Column("detail", sa.String(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=True),
        sa.Column("updated_at", sa.String(), nullable=True),
    )
    op.create_index("ix_lifecycle_audit_tenant", "lifecycle_audit", ["tenant_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_lifecycle_audit_tenant", table_name="lifecycle_audit")
    op.drop_table("lifecycle_audit")
