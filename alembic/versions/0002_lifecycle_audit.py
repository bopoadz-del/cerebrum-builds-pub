"""Lifecycle audit table (revises 0001_baseline)."""
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
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("entity", sa.String(), nullable=True),
        sa.Column("record_id", sa.Integer(), nullable=True),
        sa.Column("operation", sa.String(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("lifecycle_audit")
