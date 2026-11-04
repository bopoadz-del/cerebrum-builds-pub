"""The baseline schema: one table per capability entity plus the kernel tables.

The entity name IS the capability id -- the stem of its handler module -- so
``store.save("track_management", ...)`` finds ``track_management``. Every row
carries a ``tenant_id``: isolation is structural, not a filter a caller can skip."""


from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "track_management",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.String(length=40)),
        sa.Column("updated_at", sa.String(length=40)),
        sa.Column("reference", sa.Text()),
        sa.Column("track_key", sa.Text()),
        sa.Column("title", sa.Text()),
        sa.Column("track_version", sa.Integer()),
        sa.Column("weeks", sa.Integer()),
        sa.Column("yaml_text", sa.Text()),
        sa.Column("previous_yaml", sa.Text()),
        sa.Column("status", sa.Text()),
    )
    op.create_index("ix_track_management_tenant_id", "track_management", ["tenant_id"])
    op.create_table(
        "enrolment_and_scheduling",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.String(length=40)),
        sa.Column("updated_at", sa.String(length=40)),
        sa.Column("reference", sa.Text()),
        sa.Column("learner_email", sa.Text()),
        sa.Column("track_key", sa.Text()),
        sa.Column("start_date", sa.Text()),
        sa.Column("timezone", sa.Text()),
        sa.Column("status", sa.Text()),
    )
    op.create_index("ix_enrolment_and_scheduling_tenant_id", "enrolment_and_scheduling", ["tenant_id"])
    op.create_table(
        "ai_faculty_sessions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.String(length=40)),
        sa.Column("updated_at", sa.String(length=40)),
        sa.Column("reference", sa.Text()),
        sa.Column("session_kind", sa.Text()),
        sa.Column("kernel_mode", sa.Text()),
        sa.Column("week", sa.Text()),
        sa.Column("learner_question", sa.Text()),
        sa.Column("status", sa.Text()),
    )
    op.create_index("ix_ai_faculty_sessions_tenant_id", "ai_faculty_sessions", ["tenant_id"])
    op.create_table(
        "memo_grading",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.String(length=40)),
        sa.Column("updated_at", sa.String(length=40)),
        sa.Column("reference", sa.Text()),
        sa.Column("learner_id", sa.Text()),
        sa.Column("memo_text", sa.Text()),
        sa.Column("rubric_version", sa.Text()),
        sa.Column("word_count", sa.Integer()),
        sa.Column("status", sa.Text()),
    )
    op.create_index("ix_memo_grading_tenant_id", "memo_grading", ["tenant_id"])
    op.create_table(
        "gradebook_and_transcript",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.String(length=40)),
        sa.Column("updated_at", sa.String(length=40)),
        sa.Column("reference", sa.Text()),
        sa.Column("learner_id", sa.Text()),
        sa.Column("memos_score", sa.Text()),
        sa.Column("defenses_score", sa.Text()),
        sa.Column("capstone_score", sa.Text()),
        sa.Column("status", sa.Text()),
    )
    op.create_index("ix_gradebook_and_transcript_tenant_id", "gradebook_and_transcript", ["tenant_id"])
    op.create_table(
        "defenses_and_capstone",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.String(length=40)),
        sa.Column("updated_at", sa.String(length=40)),
        sa.Column("reference", sa.Text()),
        sa.Column("learner_id", sa.Text()),
        sa.Column("defense_date", sa.Text()),
        sa.Column("capstone_title", sa.Text()),
        sa.Column("reviewer_email", sa.Text()),
        sa.Column("verdict_count", sa.Integer()),
        sa.Column("status", sa.Text()),
    )
    op.create_index("ix_defenses_and_capstone_tenant_id", "defenses_and_capstone", ["tenant_id"])
    op.create_table(
        "library_surfaces",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.String(length=40)),
        sa.Column("updated_at", sa.String(length=40)),
        sa.Column("reference", sa.Text()),
        sa.Column("track_key", sa.Text()),
        sa.Column("week", sa.Text()),
        sa.Column("session_kind", sa.Text()),
        sa.Column("query", sa.Text()),
        sa.Column("status", sa.Text()),
    )
    op.create_index("ix_library_surfaces_tenant_id", "library_surfaces", ["tenant_id"])
    op.create_table(
        "command_center_and_chat",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.String(length=40)),
        sa.Column("updated_at", sa.String(length=40)),
        sa.Column("reference", sa.Text()),
        sa.Column("stage", sa.Text()),
        sa.Column("message", sa.Text()),
        sa.Column("status", sa.Text()),
    )
    op.create_index("ix_command_center_and_chat_tenant_id", "command_center_and_chat", ["tenant_id"])
    op.create_table(
        "work_queue",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.String(length=40)),
        sa.Column("updated_at", sa.String(length=40)),
        sa.Column("capability_id", sa.Text()),
        sa.Column("payload", sa.Text()),
        sa.Column("status", sa.Text()),
        sa.Column("attempts", sa.Integer()),
        sa.Column("result", sa.Text()),
        sa.Column("idempotency_key", sa.Text()),
    )
    op.create_index("ix_work_queue_tenant_id", "work_queue", ["tenant_id"])
    op.create_table(
        "idempotency",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.String(length=40)),
        sa.Column("updated_at", sa.String(length=40)),
        sa.Column("idempotency_key", sa.Text()),
        sa.Column("entity", sa.Text()),
        sa.Column("record_id", sa.Integer()),
    )
    op.create_index("ix_idempotency_tenant_id", "idempotency", ["tenant_id"])
    op.create_table(
        "rag_documents",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.String(length=40)),
        sa.Column("updated_at", sa.String(length=40)),
        sa.Column("source", sa.Text()),
        sa.Column("title", sa.Text()),
        sa.Column("text", sa.Text()),
        sa.Column("authority", sa.Text()),
        sa.Column("chunk_count", sa.Integer()),
    )
    op.create_index("ix_rag_documents_tenant_id", "rag_documents", ["tenant_id"])
    op.create_table(
        "rag_chunks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.String(length=40)),
        sa.Column("updated_at", sa.String(length=40)),
        sa.Column("document_id", sa.Integer()),
        sa.Column("ordinal", sa.Integer()),
        sa.Column("text", sa.Text()),
    )
    op.create_index("ix_rag_chunks_tenant_id", "rag_chunks", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_rag_chunks_tenant_id", table_name="rag_chunks")
    op.drop_table("rag_chunks")
    op.drop_index("ix_rag_documents_tenant_id", table_name="rag_documents")
    op.drop_table("rag_documents")
    op.drop_index("ix_idempotency_tenant_id", table_name="idempotency")
    op.drop_table("idempotency")
    op.drop_index("ix_work_queue_tenant_id", table_name="work_queue")
    op.drop_table("work_queue")
    op.drop_index("ix_command_center_and_chat_tenant_id", table_name="command_center_and_chat")
    op.drop_table("command_center_and_chat")
    op.drop_index("ix_library_surfaces_tenant_id", table_name="library_surfaces")
    op.drop_table("library_surfaces")
    op.drop_index("ix_defenses_and_capstone_tenant_id", table_name="defenses_and_capstone")
    op.drop_table("defenses_and_capstone")
    op.drop_index("ix_gradebook_and_transcript_tenant_id", table_name="gradebook_and_transcript")
    op.drop_table("gradebook_and_transcript")
    op.drop_index("ix_memo_grading_tenant_id", table_name="memo_grading")
    op.drop_table("memo_grading")
    op.drop_index("ix_ai_faculty_sessions_tenant_id", table_name="ai_faculty_sessions")
    op.drop_table("ai_faculty_sessions")
    op.drop_index("ix_enrolment_and_scheduling_tenant_id", table_name="enrolment_and_scheduling")
    op.drop_table("enrolment_and_scheduling")
    op.drop_index("ix_track_management_tenant_id", table_name="track_management")
    op.drop_table("track_management")
