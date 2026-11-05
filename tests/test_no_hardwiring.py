"""No programme content in product code.

Every string that is programme content -- a track's name or audience, a term
title, a week theme, a reading's title and source, a case's title, prompt or
outcome, a rubric criterion's label or description -- comes from the YAML
track files. The check reads the seeds and searches the shipped source for
each string, so it holds for a track the product has never seen: add a track
file and its content is covered without editing this test.
"""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
TRACKS = ROOT / "tracks"
SOURCE_ROOTS = (ROOT / "app",)

#: Keys whose values are programme content. Structural keys (schema_version,
#: id, number, day_offset, weights) are contract, not content.
CONTENT_KEYS = {
    "name",
    "audience",
    "title",
    "theme",
    "source",
    "note",
    "prompt",
    "outcome",
    "label",
    "description",
}


def _content_strings() -> dict[str, str]:
    """(string -> where it came from) for every content value in the seeds."""
    found: dict[str, str] = {}
    for path in sorted(TRACKS.glob("*.yaml")):
        document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        _walk(document, path.name, found)
    return found


def _walk(node, origin: str, found: dict[str, str]) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            if isinstance(value, str) and key in CONTENT_KEYS:
                text = value.strip()
                if len(text) >= 4:
                    found.setdefault(text, f"{origin}:{key}")
            else:
                _walk(value, origin, found)
    elif isinstance(node, list):
        for item in node:
            _walk(item, origin, found)


def _source_text() -> dict[Path, str]:
    files = []
    for root in SOURCE_ROOTS:
        files.extend(
            path
            for path in root.rglob("*")
            if path.is_file()
            and "__pycache__" not in path.parts
            and path.suffix in {".py", ".html", ".js", ".css", ".json"}
        )
    return {path: path.read_text(encoding="utf-8", errors="replace") for path in files}


def test_no_seed_programme_content_appears_in_product_source():
    strings = _content_strings()
    assert strings, "no track content was found to check"

    hits: list[str] = []
    for path, text in _source_text().items():
        for value, origin in strings.items():
            if value in text:
                hits.append(f"{path.relative_to(ROOT)} contains {value!r} ({origin})")

    assert not hits, "programme content hardwired into product code:\n" + "\n".join(hits)


def test_track_ids_are_not_hardwired_as_defaults():
    """A capability resolves a track from the caller or the catalogue; a seed
    id baked in as a fallback would ship one customer's programme."""
    ids = {
        str((yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("id"))
        for path in TRACKS.glob("*.yaml")
    }
    ids.discard("")
    assert ids, "no track ids were found to check"

    offenders: list[str] = []
    for path, text in _source_text().items():
        if path.suffix != ".py":
            continue
        for track_id in ids:
            if f'"{track_id}"' in text or f"'{track_id}'" in text:
                offenders.append(f"{path.relative_to(ROOT)} contains track id {track_id!r}")

    assert not offenders, "seed track ids hardwired into product code:\n" + "\n".join(offenders)
