"""Domain fields for the ops dispute action and the payout lifecycle.

``ops_back_office`` gains the dispute operation and resolution the capability
drives; ``invoicing_and_payouts`` gains the payout stage and the partial
release amount.  Both are nullable so existing rows upgrade in place.
"""

from alembic import op
import sqlalchemy as sa

revision = "0003_ops_invoicing_fields"
down_revision = "0002_lifecycle_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ops_back_office", sa.Column("dispute_action", sa.String(), nullable=True))
    op.add_column("ops_back_office", sa.Column("resolution", sa.String(), nullable=True))
    op.add_column("invoicing_and_payouts", sa.Column("payout_stage", sa.String(), nullable=True))
    op.add_column("invoicing_and_payouts", sa.Column("released_amount", sa.Float(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("invoicing_and_payouts") as batch:
        batch.drop_column("released_amount")
        batch.drop_column("payout_stage")
    with op.batch_alter_table("ops_back_office") as batch:
        batch.drop_column("resolution")
        batch.drop_column("dispute_action")
