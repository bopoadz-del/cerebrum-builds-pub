"""baseline: one table per capability entity, plus the kernel's own tables

Revision ID: 0001_baseline
Revises:
Create Date: 2026-11-08
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def _table(name: str, domain_columns) -> None:
    op.create_table(
        name,
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(length=120), nullable=False, index=True),
        sa.Column("created_at", sa.String(length=40)),
        sa.Column("updated_at", sa.String(length=40)),
        *[sa.Column(column, sa.Text()) for column in domain_columns],
    )


def upgrade() -> None:
    _table(
        "progress_claim_management",
        [
            "reference",
            "boq_item",
            "description",
            "period",
            "claimed_quantity",
            "rate",
            "gross_amount",
            "accepted_contract_amount",
            "retention_pct",
            "ipc_number",
            "status",
        ],
    )
    _table(
        "delay_damages_tracking",
        [
            "reference",
            "commencement_date",
            "assessment_date",
            "accepted_contract_amount",
            "daily_rate_pct",
            "cap_pct",
            "delay_days",
            "extension_days",
            "status",
        ],
    )
    _table(
        "qa_itp_records",
        [
            "reference",
            "boq_item",
            "inspection_lot",
            "inspection_date",
            "test_result",
            "hold_point",
            "witness_point",
            "defect_ref",
            "defect_close_out_date",
            "signoff_by",
            "taking_over_date",
            "status",
        ],
    )
    _table(
        "document_register",
        [
            "reference",
            "title",
            "document_type",
            "revision",
            "source_document",
            "revision_date",
            "checksum",
            "status",
        ],
    )
    _table(
        "contract_terms_governance",
        [
            "reference",
            "term_type",
            "value",
            "unit",
            "source_document",
            "status",
        ],
    )
    _table(
        "commercial_dashboard",
        [
            "reference",
            "period",
            "claim_status",
            "cumulative_certified",
            "retention_balance",
            "delay_exposure",
            "qa_open_items",
            "status",
        ],
    )
    _table(
        "work_queue",
        [
            "capability_id",
            "payload",
            "status",
            "attempts",
            "result",
            "idempotency_key",
        ],
    )
    _table(
        "idempotency",
        [
            "idempotency_key",
            "entity",
            "record_id",
        ],
    )


def downgrade() -> None:
    for name in (
        "idempotency",
        "work_queue",
        "commercial_dashboard",
        "contract_terms_governance",
        "document_register",
        "qa_itp_records",
        "delay_damages_tracking",
        "progress_claim_management",
    ):
        op.drop_table(name)
