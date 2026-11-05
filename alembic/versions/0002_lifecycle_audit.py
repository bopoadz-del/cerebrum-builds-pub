"""Lifecycle audit: append-only trail for record lifecycle events.

Factory revision. The v1 capability tables are untouched, so a populated
database upgrades without a data rewrite and downgrades cleanly.
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
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("entity", sa.String(length=128), nullable=False),
        sa.Column("record_id", sa.Integer(), nullable=True),
        sa.Column("event", sa.String(length=64), nullable=False),
        sa.Column("actor", sa.String(length=128), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_lifecycle_audit_tenant_entity",
        "lifecycle_audit",
        ["tenant_id", "entity"],
    )


def downgrade() -> None:
    op.drop_index("ix_lifecycle_audit_tenant_entity", table_name="lifecycle_audit")
    op.drop_table("lifecycle_audit")
