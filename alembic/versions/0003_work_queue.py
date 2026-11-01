"""v3 schema change: the persisted work queue and its idempotency ledger.

The ten domain outcomes are performed through execute_action, and two of
them (``queue_item_processed``, ``idempotent_duplicate_safe``) read and
write the queue app/work_queue.py keeps: ``work_queue`` holds one row per
enqueued item, ``idempotency`` remembers which record a replayed
idempotency key already produced. Schema belongs to alembic, so the two
tables are created here rather than at connect time; without them enqueue
and recall raise ``no such table: work_queue`` / ``idempotency`` and the
outcomes cannot be performed at all.

Revision ID: 0003_work_queue
Revises: 0002_lifecycle_audit
Create Date: 2026-10-08
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0003_work_queue"
down_revision = "0002_lifecycle_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "work_queue",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("capability_id", sa.Text(), nullable=False),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("result", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.Text(), nullable=True),
    )
    op.create_table(
        "idempotency",
        sa.Column("key", sa.Text(), primary_key=True),
        sa.Column("entity", sa.Text(), nullable=False),
        sa.Column("record_id", sa.Integer(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("idempotency")
    op.drop_table("work_queue")
