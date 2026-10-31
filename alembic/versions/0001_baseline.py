"""Baseline schema: one table per capability entity plus queue, idempotency,
and the retrieval corpus.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-10-31
"""

from alembic import op
import sqlalchemy as sa

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None

CAPABILITIES = [
    "document_grounded_qa",
    "supplier_cost_and_parts_pricing",
    "cost_price_movement_alerts",
    "document_revision_nudges",
    "document_ingestion_from_m365_and_upload",
    "manager_dashboard",
    "manager_only_access",
    "sap_odata_connector",
]


def _envelope_table(name: str) -> None:
    op.create_table(
        name,
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(), nullable=False, index=True),
        sa.Column("reference", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
    )


def upgrade() -> None:
    for name in CAPABILITIES:
        _envelope_table(name)
    _envelope_table("rag_document")
    op.create_table(
        "work_queue",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(), nullable=False, index=True),
        sa.Column("capability_id", sa.String(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("idempotency_key", sa.String(), nullable=True),
        sa.Column("result_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
    )
    op.create_table(
        "idempotency",
        sa.Column("key", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("entity", sa.String(), nullable=False),
        sa.Column("record_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("idempotency")
    op.drop_table("work_queue")
    op.drop_table("rag_document")
    for name in reversed(CAPABILITIES):
        op.drop_table(name)
