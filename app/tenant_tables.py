"""Table objects shared by the retrieval surface and the store.

Declared once so the query in app/retrieval.py and the ingest in
app/rag_routes.py use the same columns. Schema is applied by Alembic.
"""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa


def rag_table() -> Any:
    return sa.table(
        "rag_chunks",
        sa.column("id"),
        sa.column("tenant_id"),
        sa.column("document_id"),
        sa.column("chunk"),
        sa.column("tokens"),
        sa.column("created_at"),
    )
