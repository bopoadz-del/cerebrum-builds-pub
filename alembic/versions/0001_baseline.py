"""baseline schema: one table per capability entity + the kernel's own tables

Revision ID: 0001_baseline
Revises:
Create Date: 2026-09-04

Every entity the product can save a record to has one literal
``op.create_table("<entity>")`` here -- an entity's name IS its capability id,
which is also the stem of its handler module and the key its route saves under.
The column NAMES come from the same declarations the store issues its
statements against (``app.models.MODELS`` and ``app.store.INTERNAL_COLUMNS``),
so a route, a handler's ENTITY and its migrated table cannot drift apart. The
domain columns are TEXT because the store encodes every domain scalar (numbers
and booleans included) as a bound JSON parameter; the platform columns (id,
tenant_id, timestamps) are the only typed ones.

``lifecycle_audit`` is deliberately NOT here: revision 0002 adds it so the
v1 -> v2 transition in the data-lifecycle drill has real work to apply.
"""

from __future__ import annotations

from typing import List

import sqlalchemy as sa
from alembic import op

from app.models import MODELS
from app.store import INTERNAL_COLUMNS

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None

PLATFORM_COLUMNS = ("id", "tenant_id", "created_at", "updated_at")


def _columns(fields: List[str]) -> List[sa.Column]:
    """Platform columns first, then one TEXT column per domain field."""
    columns = [
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.String(length=40), nullable=True),
        sa.Column("updated_at", sa.String(length=40), nullable=True),
    ]
    for name in fields:
        if name in PLATFORM_COLUMNS:
            continue
        columns.append(sa.Column(name, sa.Text(), nullable=True))
    return columns


def _table(entity: str, fields: List[str]) -> None:
    op.create_table(entity, *_columns(fields), sa.Index("ix_" + entity + "_tenant_id", "tenant_id"))


def upgrade() -> None:
    _table("track_management", list(MODELS["track_management"].FIELDS))
    _table("enrolment_and_scheduling", list(MODELS["enrolment_and_scheduling"].FIELDS))
    _table("ai_faculty_sessions", list(MODELS["ai_faculty_sessions"].FIELDS))
    _table("memo_grading", list(MODELS["memo_grading"].FIELDS))
    _table("gradebook_and_transcript", list(MODELS["gradebook_and_transcript"].FIELDS))
    _table("defenses_and_capstone", list(MODELS["defenses_and_capstone"].FIELDS))
    _table("library_surfaces", list(MODELS["library_surfaces"].FIELDS))
    _table("command_center_and_chat", list(MODELS["command_center_and_chat"].FIELDS))
    # The kernel's own tables: its work queue, its idempotency ledger, and the
    # retrieval corpus. They are not capabilities, but they are persisted
    # through the same store and so are migrated here, with 0001.
    _table("work_queue", list(INTERNAL_COLUMNS["work_queue"]))
    _table("idempotency", list(INTERNAL_COLUMNS["idempotency"]))
    _table("rag_documents", list(INTERNAL_COLUMNS["rag_documents"]))
    _table("rag_chunks", list(INTERNAL_COLUMNS["rag_chunks"]))


def downgrade() -> None:
    for entity in (
        "rag_chunks",
        "rag_documents",
        "idempotency",
        "work_queue",
        "command_center_and_chat",
        "library_surfaces",
        "defenses_and_capstone",
        "gradebook_and_transcript",
        "memo_grading",
        "ai_faculty_sessions",
        "enrolment_and_scheduling",
        "track_management",
    ):
        op.drop_table(entity)
