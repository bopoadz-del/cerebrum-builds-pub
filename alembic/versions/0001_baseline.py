"""Baseline schema for the Harbourline contracts-administration platform.

One op.create_table per entity. The entity name IS the capability id, so
store.save("progress_claims", ...) writes the table this revision creates.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None

_TS = sa.String(length=64)


def _stamp_columns() -> list:
    return [
        sa.Column("created_at", _TS, nullable=True),
        sa.Column("updated_at", _TS, nullable=True),
    ]


def _tenant() -> sa.Column:
    return sa.Column("tenant_id", sa.String(length=64), nullable=False)


def upgrade() -> None:
    op.create_table(
        "progress_claims",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        _tenant(),
        sa.Column("reference", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=True),
        sa.Column("claim_number", sa.String(length=120), nullable=True),
        sa.Column("claim_period", sa.String(length=64), nullable=True),
        sa.Column("boq_item_code", sa.String(length=16), nullable=True),
        sa.Column("measured_quantity", sa.Float(), nullable=True),
        sa.Column("unit_rate", sa.Float(), nullable=True),
        sa.Column("accepted_contract_amount", sa.Float(), nullable=True),
        sa.Column("approval_decision", sa.String(length=32), nullable=True),
        sa.Column("approved_by", sa.String(length=120), nullable=True),
        sa.Column("certificate_note", sa.Text(), nullable=True),
        *_stamp_columns(),
    )
    op.create_table(
        "delay_damages_tracking",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        _tenant(),
        sa.Column("reference", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=True),
        sa.Column("assessment_number", sa.String(length=120), nullable=True),
        sa.Column("commencement_date", sa.String(length=32), nullable=True),
        sa.Column("completion_date", sa.String(length=32), nullable=True),
        sa.Column("days_of_delay", sa.Integer(), nullable=True),
        sa.Column("accepted_contract_amount", sa.Float(), nullable=True),
        sa.Column("notice_served", sa.Boolean(), nullable=True),
        sa.Column("assessment_note", sa.Text(), nullable=True),
        *_stamp_columns(),
    )
    op.create_table(
        "qa_itp_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        _tenant(),
        sa.Column("reference", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=True),
        sa.Column("itp_number", sa.String(length=120), nullable=True),
        sa.Column("boq_item_code", sa.String(length=16), nullable=True),
        sa.Column("inspection_type", sa.String(length=32), nullable=True),
        sa.Column("hold_point", sa.Boolean(), nullable=True),
        sa.Column("inspection_date", sa.String(length=32), nullable=True),
        sa.Column("result", sa.String(length=32), nullable=True),
        sa.Column("signed_off_by", sa.String(length=120), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        *_stamp_columns(),
    )
    op.create_table(
        "document_register",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        _tenant(),
        sa.Column("reference", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=True),
        sa.Column("document_number", sa.String(length=120), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("document_type", sa.String(length=32), nullable=True),
        sa.Column("revision", sa.String(length=32), nullable=True),
        sa.Column("source_document", sa.String(length=255), nullable=True),
        sa.Column("checksum", sa.String(length=128), nullable=True),
        sa.Column("issued_date", sa.String(length=32), nullable=True),
        sa.Column("supersedes", sa.String(length=120), nullable=True),
        *_stamp_columns(),
    )
    op.create_table(
        "retention_defects_release",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        _tenant(),
        sa.Column("reference", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=True),
        sa.Column("certificate_reference", sa.String(length=120), nullable=True),
        sa.Column("gross_certified_amount", sa.Float(), nullable=True),
        sa.Column("taking_over_date", sa.String(length=32), nullable=True),
        sa.Column("defects_notification_end_date", sa.String(length=32), nullable=True),
        sa.Column("release_stage", sa.String(length=32), nullable=True),
        sa.Column("approval_decision", sa.String(length=32), nullable=True),
        sa.Column("approved_by", sa.String(length=120), nullable=True),
        sa.Column("performance_security_amount", sa.Float(), nullable=True),
        *_stamp_columns(),
    )
    op.create_table(
        "contract_verification_gate",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        _tenant(),
        sa.Column("reference", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=True),
        sa.Column("subject_type", sa.String(length=32), nullable=True),
        sa.Column("subject_reference", sa.String(length=120), nullable=True),
        sa.Column("clause_ref", sa.String(length=16), nullable=True),
        sa.Column("boq_item_code", sa.String(length=16), nullable=True),
        sa.Column("evidence", sa.Text(), nullable=True),
        sa.Column("decision", sa.String(length=32), nullable=True),
        *_stamp_columns(),
    )
    op.create_table(
        "work_queue",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        _tenant(),
        sa.Column("capability_id", sa.String(length=64), nullable=True),
        sa.Column("payload", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=True),
        sa.Column("idempotency_key", sa.String(length=120), nullable=True),
        sa.Column("result", sa.Text(), nullable=True),
        *_stamp_columns(),
    )
    op.create_table(
        "idempotency",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        _tenant(),
        sa.Column("key", sa.String(length=120), nullable=True),
        sa.Column("entity", sa.String(length=64), nullable=True),
        sa.Column("record_id", sa.Integer(), nullable=True),
        *_stamp_columns(),
    )


def downgrade() -> None:
    for table in (
        "idempotency",
        "work_queue",
        "contract_verification_gate",
        "retention_defects_release",
        "document_register",
        "qa_itp_records",
        "delay_damages_tracking",
        "progress_claims",
    ):
        op.drop_table(table)
