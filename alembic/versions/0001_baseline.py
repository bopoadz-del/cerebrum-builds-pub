"""Baseline schema: one table per entity, the queue, idempotency, retrieval.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-11-04
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None

#: The seven capability entities. Each entity's name IS its capability id.
ENTITIES = [
    "document_register",
    "progress_claims",
    "delay_damages_tracking",
    "qa_itp_records",
    "contract_clause_governance",
    "payment_security_and_retention_ledger",
    "claims_analytics_dashboard",
]


def _record_columns():
    """Fresh column objects: one Column instance cannot belong to two tables."""
    return [
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(length=128), nullable=False, index=True),
        sa.Column("created_at", sa.String(length=40), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table("document_register", *_record_columns())
    op.create_table("progress_claims", *_record_columns())
    op.create_table("delay_damages_tracking", *_record_columns())
    op.create_table("qa_itp_records", *_record_columns())
    op.create_table("contract_clause_governance", *_record_columns())
    op.create_table("payment_security_and_retention_ledger", *_record_columns())
    op.create_table("claims_analytics_dashboard", *_record_columns())

    # Retrieval chunks share the record shape and live in the same root.
    op.create_table("retrieval_chunk", *_record_columns())

    op.create_table(
        "work_queue",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(length=128), nullable=False, index=True),
        sa.Column("capability_id", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("result", sa.Text(), nullable=True),
        sa.Column("created_at", sa.String(length=40), nullable=False),
    )

    op.create_table(
        "idempotency",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(length=128), nullable=False, index=True),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False, index=True),
        sa.Column("entity", sa.String(length=128), nullable=False),
        sa.Column("record_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.String(length=40), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("idempotency")
    op.drop_table("work_queue")
    op.drop_table("retrieval_chunk")
    for entity in reversed(ENTITIES):
        op.drop_table(entity)
