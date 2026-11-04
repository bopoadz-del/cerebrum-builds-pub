"""The shipped track files: the seed programmes and their schema.

Tracks are data, not code: a YAML file per programme, validated against
``docs/track.v1.schema.json``. The seed COO and CEO tracks ship with the
platform so a new tenant can run a real term on day one; an operator uploads
others through track_management.
"""

from __future__ import annotations

import copy
import json
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

ROOT = Path(__file__).resolve().parents[1]
TRACKS_DIR = ROOT / "docs" / "tracks"
SCHEMA_PATH = ROOT / "docs" / "track.v1.schema.json"

SESSION_TEMPLATE: List[Dict[str, Any]] = [
    {"kind": "framework", "weekday": 0, "minutes": 90},
    {"kind": "case_prep", "weekday": 1, "minutes": 60},
    {"kind": "case_class", "weekday": 2, "minutes": 120},
    {"kind": "lab", "weekday": 4, "minutes": 90},
    {"kind": "lab", "weekday": 5, "minutes": 90},
    {"kind": "exam", "weekday": 6, "minutes": 60},
]


def schema() -> Dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def track_files() -> List[Path]:
    if not TRACKS_DIR.is_dir():
        return []
    return sorted(TRACKS_DIR.glob("*.track.yaml"))


#: Parsed track files, keyed by path and invalidated by mtime. The seed files
#: ship with the image and do not change at run time; re-parsing a 16-week
#: document per request would be pure latency.
_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}
_CACHE_LOCK = threading.Lock()


def load(path: Path) -> Optional[Dict[str, Any]]:
    path = Path(path)
    key = str(path)
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return None
    with _CACHE_LOCK:
        hit = _CACHE.get(key)
        if hit is not None and hit[0] == mtime:
            return copy.deepcopy(hit[1])
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return None
    if not isinstance(data, dict):
        return None
    with _CACHE_LOCK:
        _CACHE[key] = (mtime, data)
    return copy.deepcopy(data)


def seed(track_key: str) -> Optional[Dict[str, Any]]:
    key = str(track_key or "").strip().lower()
    if not key:
        return None
    for path in track_files():
        data = load(path)
        if isinstance(data, dict) and str(data.get("track_key") or "").lower() == key:
            return data
    return None


def seeds() -> List[Dict[str, Any]]:
    out = []
    for path in track_files():
        data = load(path)
        if isinstance(data, dict):
            out.append(data)
    return out


def week_detail(document: Dict[str, Any], week: int) -> Dict[str, Any]:
    for item in (document or {}).get("weeks_detail") or []:
        if isinstance(item, dict) and int(item.get("week") or 0) == int(week):
            return item
    return {}
