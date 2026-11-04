"""The lifecycle audit table (v1 -> v2), revises the baseline.

The data-lifecycle drill upgrades a populated v1 database to this revision,
asserts the rows survived, and downgrades back to v1 -- so the revision is a
real transition, not a stamp.
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
        sa.Column("tenant_id", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.String(length=40)),
        sa.Column("updated_at", sa.String(length=40)),
        sa.Column("entity", sa.Text()),
        sa.Column("record_id", sa.Integer()),
        sa.Column("action", sa.Text()),
        sa.Column("detail", sa.Text()),
    )
    op.create_index("ix_lifecycle_audit_tenant_id", "lifecycle_audit", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_lifecycle_audit_tenant_id", table_name="lifecycle_audit")
    op.drop_table("lifecycle_audit")
