"""Baseline schema: one table per capability entity.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-11-03

The entity name IS the capability id (the stem of app/actions/<cap>.py,
also models.<Class>.ENTITY and store.COLUMNS). Values are the declarable
columns from the capability models; every table carries tenant_id because
every read and write is tenant-scoped.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


#: entity -> [(column, sqlalchemy type)]
SCHEMA = {
    "progress_claims": [
        ("reference", sa.String(255)),
        ("status", sa.String(32)),
        ("ipc_number", sa.String(255)),
        ("boq_item", sa.String(64)),
        ("period", sa.String(32)),
        ("gross_amount", sa.Float()),
        ("retention_amount", sa.Float()),
        ("net_certified", sa.Float()),
        ("currency", sa.String(16)),
    ],
    "delay_damages_tracking": [
        ("reference", sa.String(255)),
        ("status", sa.String(32)),
        ("commencement_date", sa.Date()),
        ("completion_date", sa.Date()),
        ("accepted_contract_amount", sa.Float()),
        ("delay_days", sa.Integer()),
        ("delay_damages", sa.Float()),
        ("cap_reached", sa.Boolean()),
    ],
    "qa_itp_records": [
        ("reference", sa.String(255)),
        ("status", sa.String(32)),
        ("boq_item", sa.String(64)),
        ("inspection_lot", sa.String(255)),
        ("hold_point", sa.String(255)),
        ("witness_point", sa.String(255)),
        ("test_result", sa.String(255)),
        ("inspection_date", sa.Date()),
    ],
    "document_register": [
        ("reference", sa.String(255)),
        ("status", sa.String(32)),
        ("title", sa.String(255)),
        ("revision", sa.String(64)),
        ("document_type", sa.String(64)),
        ("source_filename", sa.String(255)),
        ("checksum", sa.String(128)),
        ("issued_date", sa.Date()),
    ],
    "performance_security_tracking": [
        ("reference", sa.String(255)),
        ("status", sa.String(32)),
        ("instrument_number", sa.String(255)),
        ("accepted_contract_amount", sa.Float()),
        ("security_amount", sa.Float()),
        ("expiry_date", sa.Date()),
        ("issuer", sa.String(255)),
    ],
    "defects_notification_period": [
        ("reference", sa.String(255)),
        ("status", sa.String(32)),
        ("taking_over_date", sa.Date()),
        ("defect_ref", sa.String(255)),
        ("defect_description", sa.Text()),
        ("closeout_evidence", sa.Text()),
        ("retention_release_amount", sa.Float()),
    ],
    "claim_evidence_and_approvals": [
        ("reference", sa.String(255)),
        ("status", sa.String(32)),
        ("claim_reference", sa.String(255)),
        ("evidence_ref", sa.String(255)),
        ("preparer_id", sa.String(255)),
        ("certifier_id", sa.String(255)),
        ("decision", sa.String(64)),
        ("claim_amount", sa.Float()),
        ("retention_amount", sa.Float()),
        ("net_certified", sa.Float()),
    ],
}


def upgrade() -> None:
    for entity, columns in SCHEMA.items():
        op.create_table(
            entity,
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.String(64), nullable=False, index=True),
            *(sa.Column(name, kind, nullable=True) for name, kind in columns),
        )


def downgrade() -> None:
    for entity in reversed(list(SCHEMA)):
        op.drop_table(entity)
