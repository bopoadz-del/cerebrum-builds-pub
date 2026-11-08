"""Lifecycle audit table: one row per backup/restore/retention event."""

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
        sa.Column("event", sa.String(length=80), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.String(length=40), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("lifecycle_audit")
