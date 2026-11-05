"""Track files: the schema they are validated against, and the loader.

Programme content lives in ``tracks/*.yaml`` and nowhere else. This module
is content-free on purpose: it reads the shipped
``track.v1.schema.json`` (JSON Schema draft 2020-12), walks a candidate
document against it, and reports the offending field path. Cross-field rules
the schema language cannot state (the three weights sum to 100; the weeks in
the terms add up to ``length_weeks``) are checked here, against the same
document, and reported with the same path vocabulary.

A track file is ``tracks/<id>.<version>.yaml``; ``id`` inside the document
must match the file's id. The version is what an enrolment pins.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "track.v1.schema.json"
TRACKS_DIR = ROOT / "tracks"

_FILENAME = re.compile(r"^(?P<id>[a-z0-9][a-z0-9_-]*)\.(?P<version>v[0-9]+)\.ya?ml$")


class TrackError(ValueError):
    """A track file the schema refuses, with the field path that failed."""

    def __init__(self, field: str, message: str):
        self.field = str(field)
        self.message = str(message)
        super().__init__("%s: %s" % (self.field, self.message))

    def as_dict(self) -> Dict[str, str]:
        return {"rejected_field": self.field, "rejection_reason": "schema", "message": self.message}


def schema() -> Dict[str, Any]:
    try:
        return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise TrackError("track.v1.schema.json", "the shipped schema is unreadable: %s" % exc)


def _resolve(root: Dict[str, Any], ref: str) -> Dict[str, Any]:
    if not ref.startswith("#/"):
        raise TrackError("$ref", "only local references are supported: %s" % ref)
    node: Any = root
    for part in ref[2:].split("/"):
        if not isinstance(node, dict) or part not in node:
            raise TrackError("$ref", "unresolvable reference: %s" % ref)
        node = node[part]
    return node


def _join(path: str, key: Any) -> str:
    if isinstance(key, int):
        return "%s[%d]" % (path, key)
    return "%s.%s" % (path, key) if path else str(key)


def _type_ok(value: Any, declared: str) -> bool:
    if declared == "object":
        return isinstance(value, dict)
    if declared == "array":
        return isinstance(value, list)
    if declared == "string":
        return isinstance(value, str)
    if declared == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if declared == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if declared == "boolean":
        return isinstance(value, bool)
    return True


def _check(value: Any, node: Dict[str, Any], root: Dict[str, Any], path: str) -> None:
    if not isinstance(node, dict):
        return
    if "$ref" in node:
        _check(value, _resolve(root, str(node["$ref"])), root, path)
        return
    declared = node.get("type")
    if isinstance(declared, str) and not _type_ok(value, declared):
        raise TrackError(path, "must be of type %s" % declared)
    if "const" in node and value != node["const"]:
        raise TrackError(path, "must be %r" % (node["const"],))
    if isinstance(value, str):
        if "minLength" in node and len(value) < int(node["minLength"]):
            raise TrackError(path, "must be at least %s characters" % node["minLength"])
        pattern = node.get("pattern")
        if pattern and re.search(str(pattern), value) is None:
            raise TrackError(path, "must match %s" % pattern)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in node and value < node["minimum"]:
            raise TrackError(path, "must be >= %s" % node["minimum"])
        if "exclusiveMinimum" in node and value <= node["exclusiveMinimum"]:
            raise TrackError(path, "must be > %s" % node["exclusiveMinimum"])
    if isinstance(value, dict):
        properties = node.get("properties") or {}
        for name in node.get("required") or []:
            if name not in value or value.get(name) in (None, ""):
                raise TrackError(_join(path, name), "is required")
        if node.get("additionalProperties") is False:
            for name in value:
                if name not in properties:
                    raise TrackError(_join(path, name), "is not an allowed field here")
        for name, sub in properties.items():
            if name in value:
                _check(value[name], sub, root, _join(path, name))
    if isinstance(value, list):
        if "minItems" in node and len(value) < int(node["minItems"]):
            raise TrackError(path, "must contain at least %s item(s)" % node["minItems"])
        if "maxItems" in node and len(value) > int(node["maxItems"]):
            raise TrackError(path, "must contain at most %s item(s)" % node["maxItems"])
        items = node.get("items")
        if isinstance(items, dict):
            for index, entry in enumerate(value):
                _check(entry, items, root, _join(path, index))


def _cross_field(document: Dict[str, Any]) -> None:
    rubric = document.get("rubric") or {}
    weights = rubric.get("weights") or {}
    if weights:
        total = sum(float(weights.get(name) or 0) for name in ("memos", "defenses", "capstone"))
        if round(total, 6) != 100:
            raise TrackError(
                "rubric.weights",
                "memos + defenses + capstone must sum to 100 (got %s)" % total,
            )
    criteria = rubric.get("criteria") or []
    if criteria and len(criteria) != 5:
        raise TrackError("rubric.criteria", "must declare exactly 5 criteria")

    length = document.get("length_weeks")
    terms = document.get("terms") or []
    if isinstance(length, int) and terms:
        weeks = 0
        for term in terms:
            weeks += len(term.get("weeks") or [])
        if weeks != length:
            raise TrackError(
                "terms",
                "the terms declare %s week(s) but length_weeks is %s" % (weeks, length),
            )
        numbers = [week.get("number") for term in terms for week in (term.get("weeks") or [])]
        if numbers != list(range(1, weeks + 1)):
            raise TrackError("terms", "week numbers must run 1..%s without gaps" % weeks)


def validate(document: Any) -> Dict[str, Any]:
    """Validate a parsed track document. Raises TrackError on refusal."""
    root = schema()
    _check(document, root, root, "")
    _cross_field(document)
    return document


def parse_yaml(text: str) -> Any:
    """Parse YAML text. PyYAML is the only parser used; a syntax error is a
    refusal naming the line, never a silent empty document."""
    import yaml

    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        where = "line %s" % (mark.line + 1) if mark is not None else "yaml"
        raise TrackError("yaml", "is not valid YAML (%s)" % where)


def validate_text(text: str) -> Dict[str, Any]:
    document = parse_yaml(text)
    if not isinstance(document, dict):
        raise TrackError("", "a track file is a mapping with header, rubric and terms")
    return validate(document)


def version_of(document: Dict[str, Any]) -> str:
    """The content version: a digest an enrolment can pin."""
    canonical = json.dumps(document, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]


def _read(path: Path) -> Tuple[str, str, Dict[str, Any]]:
    match = _FILENAME.match(path.name)
    if not match:
        raise TrackError("filename", "%s is not <id>.<version>.yaml" % path.name)
    file_id, file_version = match.group("id"), match.group("version")
    document = validate_text(path.read_text(encoding="utf-8"))
    if str(document.get("id")) != file_id:
        raise TrackError("id", "the file is named %s but the document says %r" % (file_id, document.get("id")))
    return file_id, file_version, document


def track_files() -> List[Path]:
    if not TRACKS_DIR.is_dir():
        return []
    return sorted(path for path in TRACKS_DIR.iterdir() if _FILENAME.match(path.name))


def load_track(track_id: str, version: Optional[str] = None) -> Dict[str, Any]:
    """Load one track by id (optionally pinning a file version)."""
    wanted = str(track_id or "").strip()
    candidates = []
    for path in track_files():
        match = _FILENAME.match(path.name)
        if match and match.group("id") == wanted:
            candidates.append((match.group("version"), path))
    if not candidates:
        raise TrackError("track_id", "no track file named %r under tracks/" % wanted)
    if version:
        candidates = [pair for pair in candidates if pair[0] == str(version)]
        if not candidates:
            raise TrackError("track_version", "track %r has no version %r" % (wanted, version))
    file_version, path = sorted(candidates)[-1]
    _file_id, _ver, document = _read(path)
    document = dict(document)
    document["file_version"] = file_version
    document["content_version"] = version_of(document)
    document["path"] = str(path.relative_to(ROOT))
    return document


def load_all() -> List[Dict[str, Any]]:
    """Every track file, validated. A single invalid file refuses the load."""
    out: List[Dict[str, Any]] = []
    for path in track_files():
        file_id, _version, document = _read(path)
        document = dict(document)
        document["file_version"] = _version
        document["content_version"] = version_of(document)
        document["path"] = str(path.relative_to(ROOT))
        out.append(document)
    return out


def index() -> List[Dict[str, Any]]:
    """A compact catalogue for the UI and the loader's own answers."""
    entries = []
    for document in load_all():
        rubric = document.get("rubric") or {}
        entries.append(
            {
                "id": document.get("id"),
                "name": document.get("name"),
                "audience": document.get("audience"),
                "length_weeks": document.get("length_weeks"),
                "hours_per_week": document.get("hours_per_week"),
                "terms": len(document.get("terms") or []),
                "criteria": len(rubric.get("criteria") or []),
                "weights": dict(rubric.get("weights") or {}),
                "version": document.get("file_version"),
                "content_version": document.get("content_version"),
                "path": document.get("path"),
            }
        )
    return entries


def week_of(document: Dict[str, Any], week_number: int) -> Dict[str, Any]:
    """The week record a session is built from (content comes from the file)."""
    for term in document.get("terms") or []:
        for week in term.get("weeks") or []:
            if int(week.get("number") or 0) == int(week_number):
                return week
    raise TrackError("week", "track %r declares no week %s" % (document.get("id"), week_number))


def term_of_week(document: Dict[str, Any], week_number: int) -> Dict[str, Any]:
    for term in document.get("terms") or []:
        for week in term.get("weeks") or []:
            if int(week.get("number") or 0) == int(week_number):
                return term
    raise TrackError("week", "track %r declares no week %s" % (document.get("id"), week_number))


def week_numbers(document: Dict[str, Any]) -> Iterable[int]:
    for term in document.get("terms") or []:
        for week in term.get("weeks") or []:
            yield int(week.get("number") or 0)
