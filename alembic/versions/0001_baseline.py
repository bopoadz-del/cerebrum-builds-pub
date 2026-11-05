"""Baseline schema: one table per capability entity.

Every table carries the tenant column the store scopes by. The payload
itself lives in ``data`` (JSON text) so capability fields can evolve; the
columns the platform queries directly (reference, status) are lifted out.
One literal ``op.create_table`` call per entity: the migration is the
schema, not a loop over it. The platform's own system tables (queue,
idempotency, retrieval corpus) are created the same way.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "track_loader",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("reference", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=True),
        sa.Column("data", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.String(length=64), nullable=True),
        sa.Column("updated_at", sa.String(length=64), nullable=True),
    )
    op.create_index("ix_track_loader_tenant_id", "track_loader", ["tenant_id"])

    op.create_table(
        "enrolment_and_calendar",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("reference", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=True),
        sa.Column("data", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.String(length=64), nullable=True),
        sa.Column("updated_at", sa.String(length=64), nullable=True),
    )
    op.create_index("ix_enrolment_and_calendar_tenant_id", "enrolment_and_calendar", ["tenant_id"])

    op.create_table(
        "faculty_session",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("reference", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=True),
        sa.Column("data", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.String(length=64), nullable=True),
        sa.Column("updated_at", sa.String(length=64), nullable=True),
    )
    op.create_index("ix_faculty_session_tenant_id", "faculty_session", ["tenant_id"])

    op.create_table(
        "memo_grading",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("reference", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=True),
        sa.Column("data", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.String(length=64), nullable=True),
        sa.Column("updated_at", sa.String(length=64), nullable=True),
    )
    op.create_index("ix_memo_grading_tenant_id", "memo_grading", ["tenant_id"])

    op.create_table(
        "gradebook_and_transcript",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("reference", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=True),
        sa.Column("data", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.String(length=64), nullable=True),
        sa.Column("updated_at", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_gradebook_and_transcript_tenant_id", "gradebook_and_transcript", ["tenant_id"]
    )

    op.create_table(
        "defense_and_capstone",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("reference", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=True),
        sa.Column("data", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.String(length=64), nullable=True),
        sa.Column("updated_at", sa.String(length=64), nullable=True),
    )
    op.create_index("ix_defense_and_capstone_tenant_id", "defense_and_capstone", ["tenant_id"])

    op.create_table(
        "track_admin",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("reference", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=True),
        sa.Column("data", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.String(length=64), nullable=True),
        sa.Column("updated_at", sa.String(length=64), nullable=True),
    )
    op.create_index("ix_track_admin_tenant_id", "track_admin", ["tenant_id"])

    op.create_table(
        "reading_and_case_library",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("reference", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=True),
        sa.Column("data", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.String(length=64), nullable=True),
        sa.Column("updated_at", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_reading_and_case_library_tenant_id", "reading_and_case_library", ["tenant_id"]
    )

    # -- platform system tables -------------------------------------------
    op.create_table(
        "work_queue",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("reference", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=True),
        sa.Column("data", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.String(length=64), nullable=True),
        sa.Column("updated_at", sa.String(length=64), nullable=True),
    )
    op.create_index("ix_work_queue_tenant_id", "work_queue", ["tenant_id"])

    op.create_table(
        "idempotency",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("reference", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=True),
        sa.Column("data", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.String(length=64), nullable=True),
        sa.Column("updated_at", sa.String(length=64), nullable=True),
    )
    op.create_index("ix_idempotency_tenant_id", "idempotency", ["tenant_id"])

    op.create_table(
        "rag_documents",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(length=128), nullable=False),
        sa.Column("reference", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=True),
        sa.Column("data", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.String(length=64), nullable=True),
        sa.Column("updated_at", sa.String(length=64), nullable=True),
    )
    op.create_index("ix_rag_documents_tenant_id", "rag_documents", ["tenant_id"])


def downgrade() -> None:
    for table in (
        "rag_documents",
        "idempotency",
        "work_queue",
        "reading_and_case_library",
        "track_admin",
        "defense_and_capstone",
        "gradebook_and_transcript",
        "memo_grading",
        "faculty_session",
        "enrolment_and_calendar",
        "track_loader",
    ):
        op.drop_table(table)
