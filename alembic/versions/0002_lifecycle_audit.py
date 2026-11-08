"""lifecycle audit table on top of the baseline

Revision ID: 0002_lifecycle_audit
Revises: 0001_baseline
Create Date: 2026-11-08
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
        sa.Column("tenant_id", sa.String(length=120), nullable=False, index=True),
        sa.Column("created_at", sa.String(length=40)),
        sa.Column("updated_at", sa.String(length=40)),
        sa.Column("entity", sa.Text()),
        sa.Column("record_id", sa.Text()),
        sa.Column("action", sa.Text()),
        sa.Column("detail", sa.Text()),
    )


def downgrade() -> None:
    op.drop_table("lifecycle_audit")
