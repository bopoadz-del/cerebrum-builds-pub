"""baseline: one table per capability entity, tenant-scoped

Revision ID: 0001_baseline
Revises:
Create Date: 2026-11-03

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def _base(name: str):
    return [
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Text(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "progress_claims",
        *_base("progress_claims"),
        sa.Column("reference", sa.Text()),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("ipc_number", sa.Text()),
        sa.Column("boq_item", sa.Text()),
        sa.Column("period", sa.Text()),
        sa.Column("gross_amount", sa.Float()),
        sa.Column("retention_amount", sa.Float()),
        sa.Column("net_certified", sa.Float()),
        sa.Column("currency", sa.Text()),
    )
    op.create_table(
        "delay_damages_tracking",
        *_base("delay_damages_tracking"),
        sa.Column("reference", sa.Text()),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("commencement_date", sa.Text()),
        sa.Column("completion_date", sa.Text()),
        sa.Column("accepted_contract_amount", sa.Float()),
        sa.Column("delay_days", sa.Integer()),
        sa.Column("delay_damages", sa.Float()),
        sa.Column("cap_reached", sa.Integer()),
    )
    op.create_table(
        "qa_itp_records",
        *_base("qa_itp_records"),
        sa.Column("reference", sa.Text()),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("boq_item", sa.Text()),
        sa.Column("inspection_lot", sa.Text()),
        sa.Column("hold_point", sa.Text()),
        sa.Column("witness_point", sa.Text()),
        sa.Column("test_result", sa.Text()),
        sa.Column("inspection_date", sa.Text()),
    )
    op.create_table(
        "document_register",
        *_base("document_register"),
        sa.Column("reference", sa.Text()),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("title", sa.Text()),
        sa.Column("revision", sa.Text()),
        sa.Column("document_type", sa.Text()),
        sa.Column("source_filename", sa.Text()),
        sa.Column("checksum", sa.Text()),
        sa.Column("issued_date", sa.Text()),
    )
    op.create_table(
        "performance_security_tracking",
        *_base("performance_security_tracking"),
        sa.Column("reference", sa.Text()),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("instrument_number", sa.Text()),
        sa.Column("accepted_contract_amount", sa.Float()),
        sa.Column("security_amount", sa.Float()),
        sa.Column("expiry_date", sa.Text()),
        sa.Column("issuer", sa.Text()),
    )
    op.create_table(
        "defects_notification_period",
        *_base("defects_notification_period"),
        sa.Column("reference", sa.Text()),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("taking_over_date", sa.Text()),
        sa.Column("defect_ref", sa.Text()),
        sa.Column("defect_description", sa.Text()),
        sa.Column("closeout_evidence", sa.Text()),
        sa.Column("retention_release_amount", sa.Float()),
    )
    op.create_table(
        "claim_evidence_and_approvals",
        *_base("claim_evidence_and_approvals"),
        sa.Column("reference", sa.Text()),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("claim_reference", sa.Text()),
        sa.Column("evidence_ref", sa.Text()),
        sa.Column("preparer_id", sa.Text()),
        sa.Column("certifier_id", sa.Text()),
        sa.Column("decision", sa.Text()),
        sa.Column("claim_amount", sa.Float()),
        sa.Column("retention_amount", sa.Float()),
        sa.Column("net_certified", sa.Float()),
    )


def downgrade() -> None:
    for table in (
        "claim_evidence_and_approvals",
        "defects_notification_period",
        "performance_security_tracking",
        "document_register",
        "qa_itp_records",
        "delay_damages_tracking",
        "progress_claims",
    ):
        op.drop_table(table)
