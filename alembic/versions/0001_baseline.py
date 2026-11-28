"""Baseline schema for the Delivery Service Platform.

One op.create_table per capability entity. The entity name is the
capability id, exactly as app/store.py and every route use it.
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'customer_booking_flow',
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=True),
        sa.Column('reference', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('notes', sa.String(), nullable=True),
        sa.Column('customer_name', sa.String(), nullable=True),
        sa.Column('customer_email', sa.String(), nullable=True),
        sa.Column('contractor_reference', sa.String(), nullable=True),
        sa.Column('suburb', sa.String(), nullable=True),
        sa.Column('booking_date', sa.String(), nullable=True),
        sa.Column('start_time', sa.String(), nullable=True),
        sa.Column('end_time', sa.String(), nullable=True),
        sa.Column('service_type', sa.String(), nullable=True),
        sa.Column('quoted_amount', sa.Float(), nullable=True),
        sa.Column('cost_amount', sa.Float(), nullable=True),
    )
    op.create_table(
        'contractor_onboarding_and_service_areas',
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=True),
        sa.Column('reference', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('notes', sa.String(), nullable=True),
        sa.Column('contractor_name', sa.String(), nullable=True),
        sa.Column('contact_email', sa.String(), nullable=True),
        sa.Column('phone', sa.String(), nullable=True),
        sa.Column('service_suburbs', sa.String(), nullable=True),
        sa.Column('pending_suburbs', sa.String(), nullable=True),
        sa.Column('retired_suburbs', sa.String(), nullable=True),
        sa.Column('catalogue_state', sa.String(), nullable=True),
        sa.Column('vehicle_type', sa.String(), nullable=True),
        sa.Column('capacity', sa.Integer(), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=True),
    )
    op.create_table(
        'contractor_availability_schedule',
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=True),
        sa.Column('reference', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('notes', sa.String(), nullable=True),
        sa.Column('contractor_reference', sa.String(), nullable=True),
        sa.Column('weekday', sa.String(), nullable=True),
        sa.Column('start_time', sa.String(), nullable=True),
        sa.Column('end_time', sa.String(), nullable=True),
        sa.Column('capacity', sa.Integer(), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=True),
    )
    op.create_table(
        'location_based_matching',
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=True),
        sa.Column('reference', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('notes', sa.String(), nullable=True),
        sa.Column('booking_reference', sa.String(), nullable=True),
        sa.Column('suburb', sa.String(), nullable=True),
        sa.Column('contractor_reference', sa.String(), nullable=True),
        sa.Column('booking_date', sa.String(), nullable=True),
        sa.Column('start_time', sa.String(), nullable=True),
        sa.Column('distance_km', sa.Float(), nullable=True),
        sa.Column('required_skills', sa.String(), nullable=True),
    )
    op.create_table(
        'booking_status_lifecycle',
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=True),
        sa.Column('reference', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('notes', sa.String(), nullable=True),
        sa.Column('booking_reference', sa.String(), nullable=True),
        sa.Column('current_state', sa.String(), nullable=True),
        sa.Column('target_state', sa.String(), nullable=True),
        sa.Column('actor', sa.String(), nullable=True),
        sa.Column('transition_id', sa.String(), nullable=True),
    )
    op.create_table(
        'booking_notifications',
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=True),
        sa.Column('reference', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('notes', sa.String(), nullable=True),
        sa.Column('booking_reference', sa.String(), nullable=True),
        sa.Column('recipient_email', sa.String(), nullable=True),
        sa.Column('recipient_phone', sa.String(), nullable=True),
        sa.Column('channel', sa.String(), nullable=True),
        sa.Column('message', sa.String(), nullable=True),
        sa.Column('event_type', sa.String(), nullable=True),
    )
    op.create_table(
        'invoicing_and_payouts',
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=True),
        sa.Column('reference', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('notes', sa.String(), nullable=True),
        sa.Column('booking_reference', sa.String(), nullable=True),
        sa.Column('amount', sa.Float(), nullable=True),
        sa.Column('units', sa.Float(), nullable=True),
        sa.Column('payee_reference', sa.String(), nullable=True),
        sa.Column('invoice_reference', sa.String(), nullable=True),
    )
    op.create_table(
        'ops_back_office',
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=True),
        sa.Column('reference', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('notes', sa.String(), nullable=True),
        sa.Column('dispute_reference', sa.String(), nullable=True),
        sa.Column('booking_reference', sa.String(), nullable=True),
        sa.Column('claimant', sa.String(), nullable=True),
        sa.Column('claim_type', sa.String(), nullable=True),
        sa.Column('suburb', sa.String(), nullable=True),
        sa.Column('region', sa.String(), nullable=True),
        sa.Column('resolution_notes', sa.String(), nullable=True),
        sa.Column('maintain_suburbs', sa.Boolean(), nullable=True),
        sa.Column('suburb_active', sa.Boolean(), nullable=True),
    )
    op.create_table(
        'audit',
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=True),
        sa.Column('reference', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('notes', sa.String(), nullable=True),
        sa.Column('event', sa.String(), nullable=True),
        sa.Column('resource_type', sa.String(), nullable=True),
        sa.Column('resource_id', sa.String(), nullable=True),
        sa.Column('details', sa.String(), nullable=True),
        sa.Column('actor', sa.String(), nullable=True),
        sa.Column('sequence', sa.Integer(), nullable=True),
        sa.Column('previous_digest', sa.String(), nullable=True),
        sa.Column('chain_digest', sa.String(), nullable=True),
    )
    op.create_table(
        'config',
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=True),
        sa.Column('reference', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('notes', sa.String(), nullable=True),
        sa.Column('config_block', sa.String(), nullable=True),
        sa.Column('key', sa.String(), nullable=True),
        sa.Column('value', sa.String(), nullable=True),
    )
    op.create_table(
        'email',
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=True),
        sa.Column('reference', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('notes', sa.String(), nullable=True),
        sa.Column('recipient_email', sa.String(), nullable=True),
        sa.Column('subject', sa.String(), nullable=True),
        sa.Column('body', sa.String(), nullable=True),
    )
    op.create_table(
        'billing',
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=True),
        sa.Column('reference', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('notes', sa.String(), nullable=True),
        sa.Column('api_key', sa.String(), nullable=True),
        sa.Column('block_used', sa.String(), nullable=True),
        sa.Column('tokens', sa.Integer(), nullable=True),
        sa.Column('plan', sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('billing')
    op.drop_table('email')
    op.drop_table('config')
    op.drop_table('audit')
    op.drop_table('ops_back_office')
    op.drop_table('invoicing_and_payouts')
    op.drop_table('booking_notifications')
    op.drop_table('booking_status_lifecycle')
    op.drop_table('location_based_matching')
    op.drop_table('contractor_availability_schedule')
    op.drop_table('contractor_onboarding_and_service_areas')
    op.drop_table('customer_booking_flow')
