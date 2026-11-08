"""Runtime settings for Harbourline Civil Works contracts administration.

Every value is read at the point of use, never at import: CI boots
``import app.main`` with an empty environment, so a module-level read of a
required credential would abort the build. Settings the operator owns are
read here once per call and never typed into code.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional, Set

ROOT = Path(__file__).resolve().parents[1]

#: Fallback storage root for a bare local run. The deploy image always sets
#: STORAGE_PATH explicitly (see Dockerfile) and the suite forces its own.
DEFAULT_STORAGE_DIRNAME = "data"

#: The single tenant a platform-token request acts as when TENANT_TOKENS binds
#: no other. Named, not inferred from the payload.
DEFAULT_TENANT = "local"

#: The uploaded source documents are read from corpus/source_of_record.json by
#: app.sources; this module holds no document name of its own.


def storage_root() -> Path:
    raw = (os.environ.get("STORAGE_PATH") or "").strip()
    if raw:
        return Path(raw)
    return ROOT / DEFAULT_STORAGE_DIRNAME


def platform_token() -> Optional[str]:
    """The platform tenant's bearer token. Unset means fail closed (401)."""
    raw = (os.environ["PLATFORM_TOKEN"] if "PLATFORM_TOKEN" in os.environ else "").strip()
    return raw or None


def tenant_tokens() -> Dict[str, str]:
    """``TENANT_TOKENS``: comma-separated ``token:tenant_id`` pairs."""
    pairs: Dict[str, str] = {}
    raw_value = os.environ["TENANT_TOKENS"] if "TENANT_TOKENS" in os.environ else ""
    for raw in raw_value.split(","):
        item = raw.strip()
        if not item or ":" not in item:
            continue
        token, _, tenant = item.partition(":")
        token, tenant = token.strip(), tenant.strip()
        if token and tenant:
            pairs[token] = tenant
    return pairs


def approved_principals() -> Set[str]:
    """Principals allowed to sign a high-impact approval field."""
    return {
        item.strip()
        for item in (os.environ.get("APPROVED_PRINCIPALS") or "").split(",")
        if item.strip()
    }


def declared_locale() -> Dict[str, str]:
    import json

    path = ROOT / "docs" / "declared_locale.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {str(k): str(v) for k, v in (data or {}).items() if v not in (None, "")}


def sync_threadpool() -> int:
    raw = (os.environ.get("FASTAPI_SYNC_THREADPOOL") or "").strip()
    try:
        value = int(raw) if raw else 8
    except ValueError:
        value = 8
    return max(4, value)


def required_settings() -> List[str]:
    """Settings the operator must supply before the platform is usable."""
    return ["PLATFORM_TOKEN"]


def tenancy_enforced() -> bool:
    return bool(platform_token() or tenant_tokens())
