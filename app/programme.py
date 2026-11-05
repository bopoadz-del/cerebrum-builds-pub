"""Shared programme plumbing for the capability handlers.

Pure functions over the track data and the block answers: resolving which
track a request is about, publishing a content version into the version
registry idempotently, and turning a block answer into the capability's own
refusal. No handler-specific decisions live here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app import track_schema
from app.dispatch import execute, failed

ROOT = Path(__file__).resolve().parents[1]

#: A track file is a few dozen kilobytes of YAML. A one-megabyte ceiling
#: keeps a hostile or accidental upload from being parsed at all.
MAX_TRACK_BYTES = 1_000_000


def _semver(file_version: str) -> str:
    raw = str(file_version or "v1").strip().lstrip("vV")
    parts = [part for part in raw.split(".") if part.strip().isdigit()]
    while len(parts) < 3:
        parts.append("0")
    return ".".join(parts[:3])


def resolve(
    payload: Dict[str, Any],
) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
    """The track a request is about, and the catalogue it came from.

    ``track_yaml`` is validated in place; ``track_path`` must stay inside the
    shipped tracks directory; ``track_id`` loads the newest file version, or
    the pinned one. With none of them the request is about the catalogue.
    """
    data = dict(payload or {})
    text = data.get("track_yaml")
    if isinstance(text, str) and len(text) > MAX_TRACK_BYTES:
        raise track_schema.TrackError(
            "track_yaml", "is larger than %s bytes" % MAX_TRACK_BYTES
        )
    if isinstance(text, str) and text.strip():
        document = track_schema.validate_text(text)
        document = dict(document)
        document["file_version"] = str(document.get("schema_version") or "track.v1")
        document["content_version"] = track_schema.version_of(document)
        return document, []
    path = data.get("track_path")
    if isinstance(path, str) and path.strip():
        target = (ROOT / path).resolve()
        tracks_root = track_schema.TRACKS_DIR.resolve()
        if tracks_root not in target.parents and target.parent != tracks_root:
            raise track_schema.TrackError("track_path", "must point inside tracks/")
        if not target.is_file():
            raise track_schema.TrackError("track_path", "no file at %s" % path)
        document = dict(track_schema.validate_text(target.read_text(encoding="utf-8")))
        document["file_version"] = "v1"
        document["content_version"] = track_schema.version_of(document)
        document["path"] = str(target.relative_to(ROOT))
        return document, []
    track_id = str(data.get("track_id") or "").strip()
    if track_id:
        return track_schema.load_track(track_id, str(data.get("track_version") or "") or None), []
    catalogue = track_schema.index() if track_schema.track_files() else []
    if catalogue:
        first = track_schema.load_track(catalogue[0]["id"])
        return first, catalogue
    return None, []


def publish_version(track_id: str, file_version: str, changelog: List[str]) -> Dict[str, Any]:
    """Publish the track's content version, idempotently.

    The version block refuses a version it already holds; that refusal is the
    registry telling us the version is published, so it is read as success.
    Any other answer is returned to the caller unchanged.
    """
    answer = execute(
        "version",
        {
            "block_id": str(track_id),
            "version": _semver(file_version),
            "changelog": list(changelog or []),
            "dependencies": {},
        },
        action="publish_version",
    )
    if failed(answer):
        message = str((answer or {}).get("error") or "")
        if "already exists" in message.lower():
            return {"status": "success", "block": "version", "published": False, "version": _semver(file_version)}
    return answer


def refusal(capability_id: str, error: str, *, field: str = "", kind: str = "validation_error", **extra: Any) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "ok": False,
        "capability_id": capability_id,
        "error": str(error),
        "error_kind": kind,
        "authority": {"layer": 1, "label": "certified", "source": "platform_rules"},
    }
    if field:
        body["rejected_field"] = field
        body["rejection_reason"] = "schema"
    body.update(extra)
    return body


STAFF_ROLES = ("Program Director", "Registrar", "Faculty")


def is_staff(payload: Dict[str, Any]) -> bool:
    roles = (payload or {}).get("_roles") or []
    return any(str(role) in STAFF_ROLES for role in roles)


def principal(payload: Dict[str, Any]) -> str:
    data = payload or {}
    return str(data.get("_principal_id") or data.get("principal_id") or "platform-director")


def tenant(payload: Dict[str, Any]) -> str:
    return str((payload or {}).get("_tenant_id") or "local")


def term_numbers(document: Dict[str, Any]) -> List[int]:
    return [int(term.get("number") or index + 1) for index, term in enumerate(document.get("terms") or [])]
