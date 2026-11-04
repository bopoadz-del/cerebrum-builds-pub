"""Lifecycle audit table: append-only records of schema and data drills.

Revision ID: 0002_lifecycle_audit
Revises: 0001_baseline
Create Date: 2026-11-04
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
        sa.Column("tenant_id", sa.String(length=128), nullable=False, index=True),
        sa.Column("created_at", sa.String(length=40), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("lifecycle_audit")
