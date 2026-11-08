"""Baseline schema: one table per capability entity.

The entity name IS the capability id -- the stem of its handler module --
so app.store.save("<capability>", ...) and this migration cannot disagree.
Every table carries tenant_id: there is no default tenant in the store.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


PLATFORM_COLUMNS = [
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("tenant_id", sa.String(120), nullable=False),
    sa.Column("created_at", sa.String(40)),
    sa.Column("updated_at", sa.String(40)),
]


def _platform_columns():
    import copy

    return [copy.copy(column) for column in PLATFORM_COLUMNS]


def _create_contract_and_boq_source_of_record() -> None:
    op.create_table(
        "contract_and_boq_source_of_record",
        *_platform_columns(),
        sa.Column("reference", sa.Text),
        sa.Column("document_type", sa.Text),
        sa.Column("source_document", sa.Text),
        sa.Column("clause_ref", sa.Text),
        sa.Column("boq_item", sa.Text),
        sa.Column("description", sa.Text),
        sa.Column("unit", sa.Text),
        sa.Column("quantity", sa.Text),
        sa.Column("rate", sa.Text),
        sa.Column("amount", sa.Text),
        sa.Column("status", sa.Text),
        sa.Index("ix_contract_and_boq_source_of_record_tenant_id", "tenant_id"),
    )


def _create_progress_claims_and_payment_certificates() -> None:
    op.create_table(
        "progress_claims_and_payment_certificates",
        *_platform_columns(),
        sa.Column("reference", sa.Text),
        sa.Column("boq_item", sa.Text),
        sa.Column("period", sa.Text),
        sa.Column("claimed_quantity", sa.Text),
        sa.Column("gross_amount", sa.Text),
        sa.Column("accepted_contract_amount", sa.Text),
        sa.Column("retention_pct", sa.Text),
        sa.Column("ipc_number", sa.Text),
        sa.Column("status", sa.Text),
        sa.Index("ix_progress_claims_and_payment_certificates_tenant_id", "tenant_id"),
    )


def _create_delay_damages_tracking() -> None:
    op.create_table(
        "delay_damages_tracking",
        *_platform_columns(),
        sa.Column("reference", sa.Text),
        sa.Column("commencement_date", sa.Text),
        sa.Column("assessment_date", sa.Text),
        sa.Column("accepted_contract_amount", sa.Text),
        sa.Column("daily_rate_pct", sa.Text),
        sa.Column("cap_pct", sa.Text),
        sa.Column("delay_days", sa.Text),
        sa.Column("extension_days", sa.Text),
        sa.Column("status", sa.Text),
        sa.Index("ix_delay_damages_tracking_tenant_id", "tenant_id"),
    )


def _create_qa_itp_records() -> None:
    op.create_table(
        "qa_itp_records",
        *_platform_columns(),
        sa.Column("reference", sa.Text),
        sa.Column("boq_item", sa.Text),
        sa.Column("inspection_lot", sa.Text),
        sa.Column("inspection_date", sa.Text),
        sa.Column("test_result", sa.Text),
        sa.Column("hold_point", sa.Text),
        sa.Column("witness_point", sa.Text),
        sa.Column("defect_ref", sa.Text),
        sa.Column("defect_close_out_date", sa.Text),
        sa.Column("signoff_by", sa.Text),
        sa.Column("taking_over_date", sa.Text),
        sa.Column("status", sa.Text),
        sa.Index("ix_qa_itp_records_tenant_id", "tenant_id"),
    )


def _create_document_register() -> None:
    op.create_table(
        "document_register",
        *_platform_columns(),
        sa.Column("reference", sa.Text),
        sa.Column("title", sa.Text),
        sa.Column("document_type", sa.Text),
        sa.Column("revision", sa.Text),
        sa.Column("source_document", sa.Text),
        sa.Column("revision_date", sa.Text),
        sa.Column("checksum", sa.Text),
        sa.Column("status", sa.Text),
        sa.Index("ix_document_register_tenant_id", "tenant_id"),
    )


def _create_claim_review_and_dispute_resolution() -> None:
    op.create_table(
        "claim_review_and_dispute_resolution",
        *_platform_columns(),
        sa.Column("reference", sa.Text),
        sa.Column("claim_reference", sa.Text),
        sa.Column("disputed_item", sa.Text),
        sa.Column("claimed_value", sa.Text),
        sa.Column("determined_value", sa.Text),
        sa.Column("basis", sa.Text),
        sa.Column("determination", sa.Text),
        sa.Column("reviewer", sa.Text),
        sa.Column("evidence_ref", sa.Text),
        sa.Column("status", sa.Text),
        sa.Index("ix_claim_review_and_dispute_resolution_tenant_id", "tenant_id"),
    )


def _create_work_queue() -> None:
    op.create_table(
        "work_queue",
        *_platform_columns(),
        sa.Column("capability_id", sa.Text),
        sa.Column("payload", sa.Text),
        sa.Column("status", sa.Text),
        sa.Column("attempts", sa.Text),
        sa.Column("result", sa.Text),
        sa.Column("idempotency_key", sa.Text),
        sa.Index("ix_work_queue_tenant_id", "tenant_id"),
    )


def _create_idempotency() -> None:
    op.create_table(
        "idempotency",
        *_platform_columns(),
        sa.Column("idempotency_key", sa.Text),
        sa.Column("entity", sa.Text),
        sa.Column("record_id", sa.Text),
        sa.Index("ix_idempotency_tenant_id", "tenant_id"),
    )


def upgrade() -> None:
    _create_contract_and_boq_source_of_record()
    _create_progress_claims_and_payment_certificates()
    _create_delay_damages_tracking()
    _create_qa_itp_records()
    _create_document_register()
    _create_claim_review_and_dispute_resolution()
    _create_work_queue()
    _create_idempotency()


def downgrade() -> None:
    op.drop_table("idempotency")
    op.drop_table("work_queue")
    op.drop_table("claim_review_and_dispute_resolution")
    op.drop_table("document_register")
    op.drop_table("qa_itp_records")
    op.drop_table("delay_damages_tracking")
    op.drop_table("progress_claims_and_payment_certificates")
    op.drop_table("contract_and_boq_source_of_record")
