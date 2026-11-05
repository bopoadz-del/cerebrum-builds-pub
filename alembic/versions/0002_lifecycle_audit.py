"""099_lifecycle_audit

Revision ID: 0002_lifecycle_audit
Revises: 0001_baseline

Adds the lifecycle audit table the data-lifecycle drill upgrades into and
downgrades out of over populated data.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_lifecycle_audit"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lifecycle_audit",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("entity", sa.String(length=64), nullable=True),
        sa.Column("revision", sa.String(length=64), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.String(length=64), nullable=True),
        sa.Column("updated_at", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("lifecycle_audit")
