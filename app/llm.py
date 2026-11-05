"""Deterministic grounded composition for operator answers.

No network, no model call: the composer only restates fields the platform
already holds and labels which authority layer each value came from. A field it
does not have is reported missing, never guessed.
"""

from __future__ import annotations

from app.authority import authority_label


def compose(question: str, record: dict, source: str = "source_of_record") -> dict:
    fields = {
        key: value for key, value in (record or {}).items()
        if key not in ("payload_json", "tenant_id") and value not in (None, "")
    }
    missing = [] if fields else [str(question or "record")]
    return {
        "answer": " ".join(f"{key.replace('_', ' ')}: {value}." for key, value in fields.items()),
        "fields": fields,
        "missing": missing,
        "authority": authority_label(source, detail="record fields held by the platform"),
        "llm": "deterministic-grounded-composer",
    }
