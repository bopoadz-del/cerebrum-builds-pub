"""Grounded answer synthesis.

A deterministic extractive reasoner: it selects the sentences from the
retrieved passages that best cover the question, joins them, and attaches
the citation labels. No provider is contacted, so the reasoning layer keeps
working in an offline deployment; a caller-supplied model name is recorded
for provenance only.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

_WORD = re.compile(r"[a-z0-9][a-z0-9_-]*")
_STOP = {"the", "a", "an", "of", "to", "in", "on", "for", "and", "or", "is", "are",
         "was", "were", "be", "by", "with", "at", "from", "that", "this", "it", "as"}


def _terms(text: str) -> set[str]:
    return {w for w in _WORD.findall(str(text or "").lower()) if w not in _STOP and len(w) > 1}


def synthesize(question: str, sources: List[Dict[str, Any]], model: str = "offline-extractive") -> Dict[str, Any]:
    if not sources:
        return {
            "answer": "No uploaded document in this tenant covers that question. Ingest the relevant BOM, work instruction, quality procedure or supplier price list first.",
            "confidence": 0.0,
            "model": model,
            "cited": [],
        }
    wanted = _terms(question)
    chosen: List[str] = []
    cited: List[str] = []
    for index, source in enumerate(sources, start=1):
        text = str(source.get("text") or "")
        sentences = [s.strip() for s in re.split(r"(?<=[.!?;])\s+|\n+", text) if s.strip()]
        if not sentences:
            continue
        best = max(sentences, key=lambda s: len(wanted & _terms(s)))
        if not (wanted & _terms(best)) and chosen:
            continue
        label = f"[Source {index}]"
        chosen.append(f"{best} {label}")
        cited.append(label)
    if not chosen:
        best = sources[0]
        chosen.append(f"{str(best.get('text') or '')[:400]} [Source 1]")
        cited.append("[Source 1]")
    confidence = round(min(1.0, float(sources[0].get("score") or 0.0) / 8.0), 3)
    return {
        "answer": " ".join(chosen),
        "confidence": confidence,
        "model": model,
        "cited": cited,
    }
