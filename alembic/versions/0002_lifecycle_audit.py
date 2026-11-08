"""Lifecycle audit table for backup/restore drills.

Revision ID: 0002_lifecycle_audit
Revises: 0001_baseline
Create Date: 2026-11-08
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_lifecycle_audit"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lifecycle_audit",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("entity", sa.String(128), nullable=False),
        sa.Column("record_id", sa.Integer),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("actor", sa.String(256)),
        sa.Column("payload", sa.String(4000)),
        sa.Column("created_at", sa.String(64), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("lifecycle_audit")
