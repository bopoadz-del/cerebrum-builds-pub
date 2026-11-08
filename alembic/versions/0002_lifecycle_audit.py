"""Lifecycle audit table.

Records the platform's own data-lifecycle events (create/update/delete on an
entity) beside the tenant data, so a restore drill and an operator audit read
the same history. Revision 0001_baseline owns the capability schema; this
revision adds the audit surface only.
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
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("created_at", sa.String(40)),
        sa.Column("updated_at", sa.String(40)),
        sa.Column("entity", sa.Text),
        sa.Column("record_id", sa.Text),
        sa.Column("action", sa.Text),
        sa.Column("detail", sa.Text),
        sa.Index("ix_lifecycle_audit_tenant_id", "tenant_id"),
    )


def downgrade() -> None:
    op.drop_table("lifecycle_audit")
