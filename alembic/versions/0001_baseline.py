"""Baseline schema for Harbourline Civil Works.

One table per capability entity, each carrying tenant_id, plus the durable work
queue and idempotency ledger app.domain_ops uses. Schema is real DDL here; no
create_all() anywhere in the boot path.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None

ENTITIES = [
    "progress_claim_administration",
    "delay_damages_tracking",
    "qa_itp_records",
    "document_register",
]


def _entity_table(name: str) -> None:
    op.create_table(
        name,
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("reference", sa.String(256), nullable=True),
        sa.Column("status", sa.String(32), nullable=True),
        sa.Column("payload_json", sa.Text, nullable=False),
        sa.Column("created_at", sa.String(64), nullable=False),
        sa.Column("updated_at", sa.String(64), nullable=False),
    )
    op.create_index("ix_" + name + "_tenant", name, ["tenant_id"])
    op.create_index("ix_" + name + "_reference", name, ["reference"])


def upgrade() -> None:
    for entity in ENTITIES:
        _entity_table(entity)
    op.create_table(
        "work_queue",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("capability_id", sa.String(128), nullable=False),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("payload_json", sa.Text, nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("idempotency_key", sa.String(256), nullable=True),
        sa.Column("result_json", sa.Text, nullable=True),
        sa.Column("created_at", sa.String(64), nullable=False),
        sa.Column("updated_at", sa.String(64), nullable=False),
    )
    op.create_index("ix_work_queue_tenant", "work_queue", ["tenant_id"])
    op.create_index("ix_work_queue_status", "work_queue", ["status"])
    op.create_table(
        "idempotency",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("idempotency_key", sa.String(256), nullable=False, unique=True),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("entity", sa.String(128), nullable=False),
        sa.Column("record_id", sa.Integer, nullable=False),
        sa.Column("created_at", sa.String(64), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("idempotency")
    op.drop_index("ix_work_queue_status", table_name="work_queue")
    op.drop_index("ix_work_queue_tenant", table_name="work_queue")
    op.drop_table("work_queue")
    for entity in reversed(ENTITIES):
        op.drop_index("ix_" + entity + "_reference", table_name=entity)
        op.drop_index("ix_" + entity + "_tenant", table_name=entity)
        op.drop_table(entity)
