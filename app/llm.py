"""Offline answerer: extractive, no network, never fabricates."""

from __future__ import annotations

from typing import Any, Dict, List


def answer_from_snippets(question: str, snippets: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compose a grounded answer from retrieved snippets, or refuse."""
    if not snippets:
        return {
            "answer_summary": "",
            "citation": "",
            "authority": "documents",
            "grounded": False,
            "refusal": "no matching document in this tenant's corpus",
        }
    best = snippets[0]
    text = str(best.get("snippet") or "")
    return {
        "answer_summary": text[:280],
        "citation": str(best.get("citation") or ""),
        "authority": str(best.get("authority") or "documents"),
        "grounded": True,
        "refusal": None,
    }
