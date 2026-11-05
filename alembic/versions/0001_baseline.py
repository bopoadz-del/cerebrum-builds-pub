"""Baseline schema: one table per capability plus the platform work queue.

The columns are the declared contract: capability fields exactly as
app.models declares them, the tenant scope every row carries, and the
timestamps the store writes. No create_all() exists anywhere -- this
revision is the only place these tables are born.

Revision ID: 0001_baseline
Revises:
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def _envelope_columns():
    return [
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=True),
        sa.Column("updated_at", sa.String(), nullable=True),
    ]


TABLES = {
    "progress_claims": [
        ("reference", sa.String()),
        ("status", sa.String()),
        ("claim_number", sa.String()),
        ("claim_period", sa.String()),
        ("boq_item_code", sa.String()),
        ("measured_quantity", sa.Float()),
        ("unit_rate", sa.Float()),
        ("accepted_contract_amount", sa.Float()),
        ("approval_decision", sa.String()),
        ("approved_by", sa.String()),
        ("certificate_note", sa.String()),
    ],
    "delay_damages_tracking": [
        ("reference", sa.String()),
        ("status", sa.String()),
        ("assessment_number", sa.String()),
        ("commencement_date", sa.String()),
        ("completion_date", sa.String()),
        ("days_of_delay", sa.Integer()),
        ("accepted_contract_amount", sa.Float()),
        ("notice_served", sa.Boolean()),
        ("assessment_note", sa.String()),
    ],
    "qa_itp_records": [
        ("reference", sa.String()),
        ("status", sa.String()),
        ("itp_number", sa.String()),
        ("boq_item_code", sa.String()),
        ("inspection_type", sa.String()),
        ("hold_point", sa.Boolean()),
        ("inspection_date", sa.String()),
        ("result", sa.String()),
        ("signed_off_by", sa.String()),
        ("remarks", sa.String()),
    ],
    "document_register": [
        ("reference", sa.String()),
        ("status", sa.String()),
        ("document_number", sa.String()),
        ("title", sa.String()),
        ("document_type", sa.String()),
        ("revision", sa.String()),
        ("source_document", sa.String()),
        ("checksum", sa.String()),
        ("issued_date", sa.String()),
        ("supersedes", sa.String()),
    ],
    "retention_defects_release": [
        ("reference", sa.String()),
        ("status", sa.String()),
        ("certificate_reference", sa.String()),
        ("gross_certified_amount", sa.Float()),
        ("taking_over_date", sa.String()),
        ("defects_notification_end_date", sa.String()),
        ("release_stage", sa.String()),
        ("approval_decision", sa.String()),
        ("approved_by", sa.String()),
        ("performance_security_amount", sa.Float()),
    ],
    "contract_verification_gate": [
        ("reference", sa.String()),
        ("status", sa.String()),
        ("subject_type", sa.String()),
        ("subject_reference", sa.String()),
        ("clause_ref", sa.String()),
        ("boq_item_code", sa.String()),
        ("evidence", sa.String()),
        ("decision", sa.String()),
    ],
    "work_queue": [
        ("capability_id", sa.String()),
        ("payload", sa.String()),
        ("status", sa.String()),
        ("idempotency_key", sa.String()),
        ("result", sa.String()),
    ],
    "idempotency": [
        ("key", sa.String()),
        ("entity", sa.String()),
        ("record_id", sa.Integer()),
    ],
}


def upgrade() -> None:
    for table_name, fields in TABLES.items():
        op.create_table(
            table_name,
            *_envelope_columns(),
            *[sa.Column(name, kind, nullable=True) for name, kind in fields],
        )
        op.create_index(
            f"ix_{table_name}_tenant", table_name, ["tenant_id"], unique=False
        )


def downgrade() -> None:
    for table_name in reversed(list(TABLES)):
        op.drop_index(f"ix_{table_name}_tenant", table_name=table_name)
        op.drop_table(table_name)
