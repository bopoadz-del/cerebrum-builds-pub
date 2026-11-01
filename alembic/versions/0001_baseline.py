"""Baseline capability schema.

One literal op.create_table(...) per capability entity; the entity name
IS the capability id (the stem of app/actions/<capability>.py). Every
table carries tenant_id: tenancy is resolved from the authenticated
principal and scopes every row.

Written by the factory WRITER role (codewhale exec).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'collection_planning_tracking',
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column('reference', sa.Text(), nullable=False),
        sa.Column('status', sa.Text(), nullable=False),
        sa.Column('source_name', sa.Text(), nullable=False),
        sa.Column('source_type', sa.Text(), nullable=True),
        sa.Column('source_address', sa.Text(), nullable=True),
        sa.Column('pickup_lat', sa.Float(), nullable=True),
        sa.Column('pickup_lng', sa.Float(), nullable=True),
        sa.Column('pickup_date', sa.Text(), nullable=True),
        sa.Column('planned_kg', sa.Float(), nullable=True),
        sa.Column('collected_kg', sa.Float(), nullable=True),
        sa.Column('moisture_pct', sa.Float(), nullable=True),
        sa.Column('crew', sa.Text(), nullable=True),
        sa.Column('vehicle_id', sa.Text(), nullable=True),
        sa.Column('priority', sa.Text(), nullable=True),
        sa.Column('delivered_on', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.Text(), nullable=True),
    )
    op.create_table(
        'batch_production_tracking',
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column('reference', sa.Text(), nullable=False),
        sa.Column('status', sa.Text(), nullable=False),
        sa.Column('batch_code', sa.Text(), nullable=False),
        sa.Column('input_material', sa.Text(), nullable=True),
        sa.Column('input_kg', sa.Float(), nullable=True),
        sa.Column('stage', sa.Text(), nullable=False),
        sa.Column('started_on', sa.Text(), nullable=True),
        sa.Column('curing_days', sa.Integer(), nullable=True),
        sa.Column('temperature_c', sa.Float(), nullable=True),
        sa.Column('moisture_pct', sa.Float(), nullable=True),
        sa.Column('ph', sa.Float(), nullable=True),
        sa.Column('c_n_ratio', sa.Float(), nullable=True),
        sa.Column('quality_result', sa.Text(), nullable=True),
        sa.Column('output_kg', sa.Float(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.Text(), nullable=True),
    )
    op.create_table(
        'catalog_pricing_orders',
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column('reference', sa.Text(), nullable=False),
        sa.Column('status', sa.Text(), nullable=False),
        sa.Column('order_number', sa.Text(), nullable=False),
        sa.Column('customer_name', sa.Text(), nullable=False),
        sa.Column('customer_type', sa.Text(), nullable=True),
        sa.Column('product_sku', sa.Text(), nullable=False),
        sa.Column('product_name', sa.Text(), nullable=True),
        sa.Column('price_list', sa.Text(), nullable=True),
        sa.Column('quantity', sa.Float(), nullable=True),
        sa.Column('unit_price', sa.Float(), nullable=True),
        sa.Column('discount_pct', sa.Float(), nullable=True),
        sa.Column('order_date', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.Text(), nullable=True),
    )
    op.create_table(
        'invoicing_tunisian_vat',
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column('reference', sa.Text(), nullable=False),
        sa.Column('status', sa.Text(), nullable=False),
        sa.Column('invoice_number', sa.Text(), nullable=False),
        sa.Column('customer_name', sa.Text(), nullable=False),
        sa.Column('customer_tax_id', sa.Text(), nullable=True),
        sa.Column('supply_type', sa.Text(), nullable=True),
        sa.Column('quantity', sa.Float(), nullable=True),
        sa.Column('unit_price_ht', sa.Float(), nullable=True),
        sa.Column('vat_exempt', sa.Boolean(), nullable=True),
        sa.Column('vat_rate', sa.Float(), nullable=True),
        sa.Column('invoice_date', sa.Text(), nullable=True),
        sa.Column('due_date', sa.Text(), nullable=True),
        sa.Column('payment_state', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.Text(), nullable=True),
    )
    op.create_table(
        'internal_staff_access',
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column('reference', sa.Text(), nullable=False),
        sa.Column('status', sa.Text(), nullable=False),
        sa.Column('principal_id', sa.Text(), nullable=False),
        sa.Column('principal_name', sa.Text(), nullable=False),
        sa.Column('principal_email', sa.Text(), nullable=True),
        sa.Column('role', sa.Text(), nullable=False),
        sa.Column('access_state', sa.Text(), nullable=True),
        sa.Column('approved_by', sa.Text(), nullable=True),
        sa.Column('team_id', sa.Text(), nullable=True),
        sa.Column('last_seen_at', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.Text(), nullable=True),
    )
    op.create_table(
        'operational_dashboard',
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column('reference', sa.Text(), nullable=False),
        sa.Column('status', sa.Text(), nullable=False),
        sa.Column('report_date', sa.Text(), nullable=True),
        sa.Column('collections_open', sa.Integer(), nullable=True),
        sa.Column('batches_in_curing', sa.Integer(), nullable=True),
        sa.Column('orders_open', sa.Integer(), nullable=True),
        sa.Column('invoices_unpaid', sa.Integer(), nullable=True),
        sa.Column('revenue_total', sa.Float(), nullable=True),
        sa.Column('quality_failures', sa.Integer(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('operational_dashboard')
    op.drop_table('internal_staff_access')
    op.drop_table('invoicing_tunisian_vat')
    op.drop_table('catalog_pricing_orders')
    op.drop_table('batch_production_tracking')
    op.drop_table('collection_planning_tracking')
