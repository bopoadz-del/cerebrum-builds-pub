"""Managed suburb catalogue (the supporting entity the ops back office keeps).

The entity columns this pass adds (audit chain, contractor pending suburbs,
ops catalogue flags) live in the baseline 0001 so a fresh install validates
against one schema and a v1 database still upgrade/downgrade cleanly.  This
revision owns only the ``service_suburb`` table: the tenant's managed suburb
list that contractor onboarding selects from and matching validates against.
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_suburb_catalogue_audit_chain"
down_revision = "0003_ops_invoicing_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "service_suburb",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=True),
        sa.Column("reference", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("suburb", sa.String(), nullable=True),
        sa.Column("region", sa.String(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("service_suburb")
