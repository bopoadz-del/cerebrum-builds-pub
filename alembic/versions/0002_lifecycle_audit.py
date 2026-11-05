"""lifecycle audit trail

Revision ID: 0002_lifecycle_audit
Revises: 0001_baseline
Create Date: 2026-09-04

Adds the append-only lifecycle audit table the data-lifecycle drill upgrades
to over a populated v1 database. Downgrade removes exactly that table and
leaves v1 rows untouched.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from app.store import INTERNAL_COLUMNS

revision = "0002_lifecycle_audit"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None

ENTITY = "lifecycle_audit"


def upgrade() -> None:
    fields = list(INTERNAL_COLUMNS[ENTITY])
    op.create_table(
        ENTITY,
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.String(length=40), nullable=True),
        sa.Column("updated_at", sa.String(length=40), nullable=True),
        *[sa.Column(name, sa.Text(), nullable=True) for name in fields],
        sa.Index("ix_" + ENTITY + "_tenant_id", "tenant_id"),
    )


def downgrade() -> None:
    op.drop_table(ENTITY)
