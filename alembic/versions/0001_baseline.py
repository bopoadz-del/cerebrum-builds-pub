"""Baseline: one table per capability entity, each tenant-scoped.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-11-08
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def _tenant() -> sa.Column:
    return sa.Column("tenant_id", sa.String(128), nullable=False)


def upgrade() -> None:
    op.create_table(
        "contract_source_of_record",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        _tenant(),
        sa.Column("reference", sa.String(256)),
        sa.Column("status", sa.String(32)),
        sa.Column("document_ref", sa.String(512)),
        sa.Column("document_kind", sa.String(32)),
        sa.Column("clause_ref", sa.String(64)),
        sa.Column("clause_title", sa.String(256)),
        sa.Column("pinned_value", sa.String(512)),
        sa.Column("version", sa.String(64)),
        sa.Column("effective_date", sa.String(32)),
        sa.Column("source_digest", sa.String(128)),
    )
    op.create_table(
        "rag_chunks",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("document_id", sa.String(256)),
        sa.Column("chunk", sa.Text),
        sa.Column("tokens", sa.Text),
        sa.Column("created_at", sa.String(64)),
    )
    op.create_table(
        "work_queue",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("capability_id", sa.String(128), nullable=False),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("payload", sa.Text),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("result", sa.Text),
        sa.Column("idempotency_key", sa.String(256)),
    )
    op.create_table(
        "idempotency",
        sa.Column("key", sa.String(256), primary_key=True),
        sa.Column("entity", sa.String(128), nullable=False),
        sa.Column("record_id", sa.Integer, nullable=False),
    )
    op.create_table(
        "progress_claims",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        _tenant(),
        sa.Column("reference", sa.String(256)),
        sa.Column("status", sa.String(32)),
        sa.Column("ipc_number", sa.String(128)),
        sa.Column("period", sa.String(64)),
        sa.Column("boq_item", sa.String(64)),
        sa.Column("measured_quantity", sa.Float),
        sa.Column("unit_rate", sa.Float),
        sa.Column("retention_percent", sa.Float),
        sa.Column("taking_over", sa.Integer),
        sa.Column("defects_notified", sa.Integer),
        sa.Column("certified_amount", sa.Float),
        sa.Column("notes", sa.String(2000)),
    )
    op.create_table(
        "delay_damages_tracking",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        _tenant(),
        sa.Column("reference", sa.String(256)),
        sa.Column("status", sa.String(32)),
        sa.Column("commencement_date", sa.String(32)),
        sa.Column("as_of_date", sa.String(32)),
        sa.Column("accepted_contract_amount", sa.Float),
        sa.Column("extension_days", sa.Integer),
        sa.Column("daily_rate_percent", sa.Float),
        sa.Column("cap_percent", sa.Float),
        sa.Column("taking_over", sa.Integer),
        sa.Column("notify_channel", sa.String(32)),
        sa.Column("notes", sa.String(2000)),
    )
    op.create_table(
        "qa_itp_records",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        _tenant(),
        sa.Column("reference", sa.String(256)),
        sa.Column("status", sa.String(32)),
        sa.Column("itp_number", sa.String(128)),
        sa.Column("boq_item", sa.String(64)),
        sa.Column("inspection_type", sa.String(128)),
        sa.Column("hold_point", sa.Integer),
        sa.Column("witness_point", sa.Integer),
        sa.Column("inspection_date", sa.String(32)),
        sa.Column("result", sa.String(32)),
        sa.Column("evidence_ref", sa.String(512)),
        sa.Column("signed_off_by", sa.String(256)),
        sa.Column("notes", sa.String(2000)),
    )
    op.create_table(
        "document_register",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        _tenant(),
        sa.Column("reference", sa.String(256)),
        sa.Column("status", sa.String(32)),
        sa.Column("document_number", sa.String(128)),
        sa.Column("document_type", sa.String(64)),
        sa.Column("title", sa.String(512)),
        sa.Column("revision", sa.String(64)),
        sa.Column("issued_by", sa.String(256)),
        sa.Column("issued_date", sa.String(32)),
        sa.Column("source_document", sa.String(512)),
        sa.Column("checksum", sa.String(128)),
        sa.Column("distribution", sa.String(512)),
    )
    op.create_table(
        "contract_compliance_gate",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        _tenant(),
        sa.Column("reference", sa.String(256)),
        sa.Column("status", sa.String(32)),
        sa.Column("submission_ref", sa.String(256)),
        sa.Column("submission_type", sa.String(64)),
        sa.Column("clause_ref", sa.String(64)),
        sa.Column("requirement", sa.String(512)),
        sa.Column("proposed_value", sa.String(512)),
        sa.Column("decision", sa.String(32)),
        sa.Column("checked_by", sa.String(256)),
    )


def downgrade() -> None:
    for name in (
        "contract_compliance_gate",
        "document_register",
        "qa_itp_records",
        "delay_damages_tracking",
        "progress_claims",
        "idempotency",
        "work_queue",
        "rag_chunks",
        "contract_source_of_record",
    ):
        op.drop_table(name)
