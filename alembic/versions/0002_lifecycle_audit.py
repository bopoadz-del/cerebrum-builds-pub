"""Lifecycle audit table: every persisted write can be traced.

Revision ID: 0002_lifecycle_audit
Revises: 0001_baseline
Create Date: 2026-11-03

Additive only: it never touches the capability tables, so upgrading a
populated v1 database leaves the rows exactly as they were, and the
downgrade drops only what this revision created.
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
        sa.Column("tenant_id", sa.String(64), nullable=False, index=True),
        sa.Column("entity", sa.String(128), nullable=False),
        sa.Column("record_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("created_at", sa.String(64), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("lifecycle_audit")
