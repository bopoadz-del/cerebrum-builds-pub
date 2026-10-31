#!/usr/bin/env python3
"""Store-green acceptance — ≥12 measured checks. Presence-only is a fail.

Authorship floor is the LAST line. HTTP 200 ok:false is not a pass.
RAG skip policy: SKIP:no-rag-surface only when the product has no RAG
route or rag capability. Steward must plant + hit.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import sys
import uuid
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

#: The product's RUNTIME tree -- what a runtime check judges and where the
#: harness serves ``app.main`` from. The Store gate runs this harness from the
#: mounted checkout and names the image's working directory here; unset (the
#: writer's --self-check, a local run) it is the tree this harness sits in.
RUNTIME_ROOT_ENV = 'ACCEPTANCE_RUNTIME_ROOT'
ROOT = Path(os.environ.get(RUNTIME_ROOT_ENV) or Path(__file__).resolve().parents[1]).resolve()

#: Where the Store gate mounts the product's CHECKOUT inside the image, named
#: by this env variable (the gate reads the name from this constant). A check
#: whose declared subject is the repository (REPO_CHECKS: ``tree:`` and
#: ``factory_record``) reads its files there, because the image is not the
#: repository: a .dockerignore may leave CI wiring, docs or tests out of the
#: image, and that is the product's call. Unset (the writer's own run, a local
#: run) the checkout IS the directory this harness sits in.
REPO_ROOT_ENV = 'ACCEPTANCE_REPO_ROOT'
REPO = Path(os.environ.get(REPO_ROOT_ENV) or ROOT).resolve()
#: The tree the running check reads files from: REPO for a repository-subject
#: check, the image (ROOT) for a runtime one. Set per check by main().
SRC = ROOT

#: ``python scripts/acceptance.py --self-check`` is the WRITER's run of this
#: same harness on its own box. Three inputs exist only where the Store gate
#: runs (a Docker daemon, a Postgres service, the bandit/pip-audit scan) and
#: arrive as STORE_* env values the gate exports. In a self-check an UNSET one
#: is reported SKIP with that reason -- never PASS. At the gate the flag is
#: never passed, so unmeasured stays a FAIL; a measured bad value fails both.
SELF_CHECK = "--self-check" in sys.argv[1:]


def _only_the_gate_measures(var):
    """SKIP line for a gate-only input left unset in a self-check, else None."""
    if SELF_CHECK and not (os.environ.get(var) or "").strip():
        return "SKIP", "%s is measured only by the Store gate (Docker/Postgres/scan); the gate still scores it" % var
    return None
#: sha256 of the Factory's own full-suite CI workflow (LF-normalised).
CI_SHA256 = '4c596b172c9855ff56fa373af43fbe290378deb99b09490716b3413dbec50e32'


def _parse(path: Path) -> Optional[ast.AST]:
    try:
        return ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    except (OSError, SyntaxError, ValueError):
        return None


def _dotted(expr: ast.AST) -> str:
    parts: List[str] = []
    while isinstance(expr, ast.Attribute):
        parts.append(expr.attr)
        expr = expr.value
    if isinstance(expr, ast.Name):
        parts.append(expr.id)
        return ".".join(reversed(parts))
    return ""


def _aliases(tree: ast.AST) -> Dict[str, str]:
    """Local name -> the module or object an import bound it to."""
    out: Dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                out[a.asname or a.name.split(".")[0]] = a.name if a.asname else a.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom):
            mod = "." * node.level + (node.module or "")
            for a in node.names:
                out[a.asname or a.name] = (mod + "." + a.name) if mod else a.name
    return out


def _callees(tree: ast.AST) -> List[Tuple[str, ast.Call]]:
    """(callee resolved through the module's imports, call) for every call."""
    alias = _aliases(tree)
    out: List[Tuple[str, ast.Call]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = _dotted(node.func)
            if name:
                head, _, rest = name.partition(".")
                base = alias.get(head, head)
                out.append((base + ("." + rest if rest else ""), node))
    return out


def _env_reads(tree: ast.AST) -> set:
    """Environment keys the module reads (os.environ.get / os.getenv /
    os.environ[...]), by constant key."""
    keys: set = set()
    readers = {"os.environ.get", "os.getenv"}
    for name, call in _callees(tree):
        if name in readers and call.args and isinstance(call.args[0], ast.Constant):
            keys.add(call.args[0].value)
    alias = _aliases(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant):
            head, _, rest = _dotted(node.value).partition(".")
            if (alias.get(head, head) + ("." + rest if rest else "")) == "os.environ":
                keys.add(node.slice.value)
    return keys


def _imports_module(tree: ast.AST, dotted: str) -> bool:
    """Does the module import ``dotted`` -- absolutely, from its parent
    package, or as a relative sibling?"""
    parent, _, leaf = dotted.rpartition(".")
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(a.name == dotted for a in node.names):
            return True
        if isinstance(node, ast.ImportFrom):
            names = {a.name for a in node.names}
            if node.level == 0 and node.module == dotted:
                return True
            if node.level == 0 and node.module == parent and leaf in names:
                return True
            if node.level >= 1 and (node.module == leaf or (not node.module and leaf in names)):
                return True
    return False


class _Tags(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tags: set = set()

    def handle_starttag(self, tag, attrs):  # noqa: ARG002 -- tags only
        self.tags.add(tag.lower())


CHECKS = ['no_token_401', 'missing_field_422', 'enum_422', 'ui_served_200', 'rag_roundtrip_hit', 'single_persistence_root', 'ci_present_and_full_suite', 'handler_bodies_distinct', 'health_fail_closed', 'openapi_committed', 'docker_health_200', 'cross_tenant_404', 'concurrent_writes_hold', 'migration_no_create_all', 'negative_floor', 'postgres_boot_200', 'one_live_connector', 'metrics_served', 'backup_restore_roundtrip', 'bench_p95', 'audit_clean', 'no_token_literal', 'authorship_floor']
# Reported and scored, never a veto -- same source as CHECKS (the floor file).
ADVISORY = ['audit_clean', 'backup_restore_roundtrip', 'bench_p95', 'one_live_connector']
# Checks judged on the built image (the floor's ``stage: image``). When the
# product's Dockerfile does not build, the Store gate scores THESE as FAIL and
# the rest NOT_RUN, reading this constant -- the gate names no check itself.
IMAGE_CHECKS = ['docker_health_200']
# Checks whose verdict is the gate's security scan (the floor's ``stage:
# audit``). The gate attaches the scan's findings to THESE lines as evidence,
# reading this constant -- it names no check itself.
AUDIT_CHECKS = ['audit_clean']
# Checks whose declared subject is the repository, not the running image (the
# floor's ``subject: tree:<path>`` and ``factory_record``): their files are read
# from REPO. Same source as CHECKS; no check is named here.
REPO_CHECKS = ['single_persistence_root', 'ci_present_and_full_suite', 'handler_bodies_distinct', 'openapi_committed', 'migration_no_create_all', 'negative_floor', 'backup_restore_roundtrip', 'audit_clean', 'no_token_literal', 'authorship_floor']
REQUIRED =23
# Keys of the typed records the Factory reads from this harness's stdout --
# the same constants the Factory's parser uses (store_acceptance.py).
RECORD_KEY = 'acceptance_record'
TOTAL_KEY = 'acceptance_total'
# The build's retrieval contract, rendered by the Factory from its blueprint:
# whether a capability binds a block that declares the vector-store read, and
# the platform's RAG routes. Never inferred from names or words at run time.
RETRIEVES = True
RAG_INGEST_PATHS = ['/v1/rag/ingest']
RAG_QUERY_PATHS = ['/v1/rag/query']
# The ingest body fields the brief declares for the document text.
RAG_INGEST_TEXT_FIELDS = ('text', 'content', 'paragraph')
# How long the harness waits for the service it starts to answer.
SERVE_TIMEOUT_S = 60
# The extra tenants the isolation check reads and writes as. The service the
# harness starts is a separate process, so it is started with them bound.
# Per-run tokens: a fixed token here would be a credential in every built image.
CHECK_TENANT_TOKENS = "token-a-" + os.urandom(8).hex() + ":tenant-a" + "," + "token-b-" + os.urandom(8).hex() + ":tenant-b"  # generated per run, never a fixed value


def _token() -> str:
    return (os.environ.get("PLATFORM_TOKEN") or "dev-local-token").strip()


def _auth() -> Dict[str, str]:
    return {"Authorization": "Bearer " + _token()}


class _Http:
    def __init__(self, client: Any):
        self.client = client

    def request(self, method: str, path: str, **kw: Any) -> Any:
        fn = getattr(self.client, method.lower())
        return fn(path, **kw)


class _Resp:
    def __init__(self, status, body, headers):
        self.status_code = int(status)
        self._body = body or b""
        self.headers = headers or {}
        self.content = self._body

    def json(self):
        return json.loads(self._body.decode("utf-8") or "{}")

    @property
    def text(self) -> str:
        return self._body.decode("utf-8", errors="replace")


class _Url:
    """Standard-library HTTP against a running service.

    This harness runs INSIDE the image, where only the runtime requirements
    are installed. An in-process test client is a test-only library (it needs
    an HTTP client package the image never declares): live, an upstream
    release moved that dependency and every in-image run crashed before its
    first check. urllib is always there."""

    def __init__(self, base: str):
        self.base = base

    def request(self, method: str, path: str, json=None, headers=None, **_kw):
        import json as _json
        import urllib.error
        import urllib.request

        data = None
        hdrs = dict(headers or {})
        if json is not None:
            data = _json.dumps(json).encode("utf-8")
            hdrs.setdefault("Content-Type", "application/json")
        req = urllib.request.Request(self.base + path, data=data, headers=hdrs, method=method.upper())
        try:
            with urllib.request.urlopen(req, timeout=_kw.get("timeout") or 8) as resp:
                return _Resp(resp.status, resp.read(), resp.headers)
        except urllib.error.HTTPError as exc:
            return _Resp(exc.code, exc.read(), exc.headers)

    def get(self, path, **kw):
        return self.request("GET", path, **kw)

    def post(self, path, **kw):
        return self.request("POST", path, **kw)


class _Down:
    """The service never answered: every HTTP check fails with the reason;
    checks that read the tree still run."""

    def __init__(self, reason: str):
        self.reason = reason

    def get(self, path, **_kw):
        raise RuntimeError(self.reason)

    post = get


class _Served:
    """The service this harness started for itself; stopped on exit."""

    def __init__(self, proc: Any):
        self.proc = proc

    def __exit__(self, *_exc: Any) -> None:
        self.proc.terminate()
        try:
            self.proc.wait(timeout=10)
        except Exception:
            self.proc.kill()


def _free_port() -> int:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _serve_env() -> Dict[str, str]:
    env = dict(os.environ)
    bound = (env.get("TENANT_TOKENS") or "").strip()
    env["TENANT_TOKENS"] = (bound + "," if bound else "") + CHECK_TENANT_TOKENS
    return env


def _serve() -> Tuple[str, _Served]:
    """Start the product's own app under its declared server (uvicorn, a
    runtime requirement) on a free local port, and wait until it answers.

    Any HTTP answer -- even an error status -- means it is serving; what that
    answer says is a check's verdict, not the harness's."""
    import subprocess
    import tempfile
    import time
    import urllib.error
    import urllib.request

    port = _free_port()
    base = "http://127.0.0.1:%d" % port
    log = tempfile.TemporaryFile()
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
         "--port", str(port), "--log-level", "warning", "--no-access-log"],
        cwd=str(ROOT), env=_serve_env(), stdout=log, stderr=subprocess.STDOUT,
    )
    served = _Served(proc)
    deadline = time.monotonic() + SERVE_TIMEOUT_S
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            log.seek(0)
            tail = log.read().decode("utf-8", errors="replace")[-1500:]
            raise RuntimeError("the service exited %s before answering: %s" % (proc.returncode, tail))
        try:
            with urllib.request.urlopen(base + "/health", timeout=2):
                return base, served
        except urllib.error.HTTPError:
            return base, served
        except Exception:
            time.sleep(0.2)
    served.__exit__(None, None, None)
    raise RuntimeError("the service did not answer within %ss" % SERVE_TIMEOUT_S)


def _client() -> Tuple[_Http, Any]:
    base = (os.environ.get("ACCEPTANCE_BASE_URL") or "").rstrip("/")
    if base:
        return _Http(_Url(base)), None
    try:
        base, served = _serve()
    except Exception as exc:
        return _Http(_Down("%s: %s" % (type(exc).__name__, exc))), None
    return _Http(_Url(base)), served


def _cap_order() -> List[str]:
    receipt = SRC / "docs" / "coder_receipt.json"
    if receipt.is_file():
        try:
            data = json.loads(receipt.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        caps = data.get("capabilities") or []
        if caps:
            out = []
            for item in caps:
                if isinstance(item, dict):
                    item = item.get("id") or item.get("capability_id") or ""
                if str(item).strip():
                    out.append(str(item))
            if out:
                return out
    try:
        from app.jobs import CAPABILITIES

        out = []
        for item in CAPABILITIES or []:
            if isinstance(item, dict) and item.get("id"):
                out.append(str(item["id"]))
            elif isinstance(item, str) and item.strip():
                out.append(item)
        if out:
            return out
    except Exception:
        pass
    try:
        from app.models import MODELS

        return sorted(MODELS or {})
    except Exception:
        return []


def _first_cap() -> str:
    """The capability the HTTP checks write through.

    A capability whose connector is a DECLARED placeholder answers the typed
    unavailable refusal and stores nothing (app/placeholders.py), so a check
    that needs a stored record writes through the first one that works.
    """
    order = _cap_order()
    try:
        from app.placeholders import PLACEHOLDER_CONNECTORS
    except Exception:
        PLACEHOLDER_CONNECTORS = {}
    for cap in order:
        if not PLACEHOLDER_CONNECTORS.get(cap):
            return cap
    return order[0] if order else ""


def _models():
    try:
        from app.models import MODELS

        return MODELS
    except Exception:
        return {}


def _required_and_enum(cap_id: str) -> Tuple[Optional[str], Optional[Tuple[str, List[Any]]]]:
    """The required field and the vocabulary field THIS capability's own model
    declares. Never another model's field: posting capability X a field only
    model Y declares measures nothing X promised (the route may ignore it)."""
    models = _models()
    cls = models.get(cap_id) if cap_id else None
    required = None
    enum = None
    if cls is not None:
        fields = list(getattr(cls, "FIELDS", []) or [])
        constraints = getattr(cls, "CONSTRAINTS", {}) or {}
        for name in fields:
            rules = constraints.get(name) or {}
            if rules.get("required") and required is None:
                required = name
            allowed = rules.get("allowed_values") or []
            if allowed and enum is None:
                enum = (name, list(allowed))
    return required, enum


def _cap_declaring(want: str) -> Tuple[str, Any]:
    """(capability, declaration) for the first working capability whose own
    model declares ``want`` -- "required" or "enum". Declared placeholders
    answer their typed refusal before validation, so they cannot be measured
    here. ("", None) when no capability declares it."""
    try:
        from app.placeholders import PLACEHOLDER_CONNECTORS
    except Exception:
        PLACEHOLDER_CONNECTORS = {}
    for cap in _cap_order():
        if PLACEHOLDER_CONNECTORS.get(cap):
            continue
        required, enum = _required_and_enum(cap)
        found = required if want == "required" else enum
        if found:
            return cap, found
    return "", None


def check_no_token_401(http: _Http) -> Tuple[str, str]:
    cap = _first_cap()
    if not cap:
        return "FAIL", "no first capability to POST"
    resp = http.request("post", "/v1/" + cap, json={})
    if resp.status_code == 401:
        return "PASS", "HTTP 401"
    if resp.status_code in (200,):
        body = {}
        try:
            body = resp.json()
        except Exception:
            pass
        return "FAIL", "HTTP %s ok:%s (must be 401, not ok:false)" % (resp.status_code, body.get('ok'))
    return "FAIL", "HTTP %s (want 401)" % resp.status_code


def check_missing_field_422(http: _Http) -> Tuple[str, str]:
    # Measured on a capability whose OWN model declares a required field.
    cap, required = _cap_declaring("required")
    if not cap:
        return "FAIL", "no capability declares a required field to measure (not a presence skip)"
    resp = http.request("post", "/v1/" + cap, json={}, headers=_auth())
    if resp.status_code == 422:
        return "PASS", "HTTP 422 missing %s" % required
    return "FAIL", "HTTP %s (want 422 for missing %s on %s)" % (resp.status_code, required, cap)


def check_enum_422(http: _Http) -> Tuple[str, str]:
    # Measured on a capability whose OWN model declares the vocabulary, with
    # the shared payload builder filling every other required field from that
    # model -- so the only thing wrong with the payload is the measured value.
    cap, enum = _cap_declaring("enum")
    if not cap:
        return "FAIL", "no capability declares an enum field to measure (not a presence skip)"
    name, _allowed = enum
    payload = dict(_sample_payload_for(cap, {}))
    payload[name] = "__not_in_contract__"
    resp = http.request("post", "/v1/" + cap, json=payload, headers=_auth())
    if resp.status_code == 422:
        return "PASS", "HTTP 422 invalid %s" % name
    return "FAIL", "HTTP %s (want 422 for invalid enum %s on %s)" % (resp.status_code, name, cap)


def check_ui_served_200(http: _Http) -> Tuple[str, str]:
    resp = http.request("get", "/")
    if resp.status_code != 200:
        return "FAIL", "GET / HTTP %s" % resp.status_code
    text = getattr(resp, "text", "") or ""
    ctype = ""
    headers = getattr(resp, "headers", {}) or {}
    if hasattr(headers, "get"):
        ctype = str(headers.get("content-type") or headers.get("Content-Type") or "")
    # The media type, or an <html> element the HTML parser actually finds.
    media = ctype.split(";", 1)[0].strip().lower()
    tags = _Tags()
    try:
        tags.feed(text)
    except Exception:  # noqa: BLE001 -- unparseable is simply not HTML
        pass
    if media == "text/html" or "html" in tags.tags:
        return "PASS", "GET / HTTP 200 HTML"
    return "FAIL", "GET / was 200 but not served UI (content-type=%s)" % ctype


def _contract_routes(contract: List[str]) -> List[str]:
    """The contract's routes, plus every POST route the PRODUCT declares in its
    committed openapi.json whose path ends with the same segments -- the same
    route mounted under a prefix. Matched by path shape, never by words."""
    out = list(contract)
    tails = [[s for s in str(p).split("/") if s][1:] for p in contract]
    try:
        doc = json.loads((SRC / "docs" / "openapi.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return out
    for path, ops in (doc.get("paths") or {}).items():
        if not isinstance(ops, dict) or "post" not in {str(k).lower() for k in ops}:
            continue
        segs = [s for s in str(path).split("/") if s]
        if any(tail and segs[-len(tail):] == tail for tail in tails) and path not in out:
            out.append(path)
    return out


def check_rag_roundtrip_hit(http: _Http) -> Tuple[str, str]:
    if not RETRIEVES:
        return "SKIP", "no capability binds a block that declares the retrieval read"
    # The nonce identifies the planted content and MUST NEVER be sent as part
    # of the query request itself -- a prior version queried the exact phrase
    # it POSTed (and even resent the planted "text" in the query body), so any
    # endpoint that echoed its own request back (idiomatic REST design, not a
    # bug) satisfied this check regardless of whether retrieval ran at all.
    # A second, never-planted nonce is the negative control: a query for it
    # must come back EMPTY, or the "hit" mechanism is proven to be an echo.
    nonce = uuid.uuid4().hex[:12]
    absent_nonce = uuid.uuid4().hex[:12]
    marker = "ACCEPTANCE-PLANT-%s the reorder threshold procedure" % nonce
    ingest_paths = _contract_routes(RAG_INGEST_PATHS)
    planted = False
    for path in ingest_paths:
        resp = http.request(
            "post",
            path,
            json={field: marker for field in RAG_INGEST_TEXT_FIELDS},
            headers=_auth(),
        )
        if resp.status_code in (200,):
            planted = True
            break
    if not planted:
        return "FAIL", "RAG surface present but plant did not accept"
    query_paths = _contract_routes(RAG_QUERY_PATHS)

    def _content_hit(resp: Any, needle: str, sent: Dict[str, Any]) -> bool:
        # Retrieved content only: every top-level field whose value is exactly
        # something the request sent is the request echoed back and is
        # dropped, then the rest of the answer is searched. No field name is
        # assumed -- an endpoint that only echoes has nothing left to search.
        if resp.status_code != 200:
            return False
        try:
            data = resp.json()
        except Exception:
            return False
        if isinstance(data, list):
            return needle in json.dumps(data).lower()
        if not isinstance(data, dict):
            return False
        echoed = {json.dumps(v, sort_keys=True) for v in sent.values()}
        kept = {
            k: v for k, v in data.items()
            if json.dumps(v, sort_keys=True) not in echoed
        }
        return needle in json.dumps(kept).lower()

    positive_hit = False
    negative_leak = False
    for path in query_paths:
        pos_sent = {"q": marker, "query": marker}
        pos_resp = http.request("post", path, json=pos_sent, headers=_auth())
        if _content_hit(pos_resp, nonce.lower(), pos_sent):
            positive_hit = True
        neg_sent = {"q": absent_nonce, "query": absent_nonce}
        neg_resp = http.request("post", path, json=neg_sent, headers=_auth())
        if _content_hit(neg_resp, absent_nonce.lower(), neg_sent):
            negative_leak = True
        if positive_hit or negative_leak:
            break
    if negative_leak:
        return "FAIL", "query for a never-planted term still came back as a hit (echo, not retrieval)"
    if positive_hit:
        return "PASS", "plant->retrieve round trip confirmed in a content field, not a request echo"
    return "FAIL", "RAG surface present but query missed"


def check_single_persistence_root() -> Tuple[str, str]:
    store = SRC / "app" / "store.py"
    if not store.is_file():
        return "FAIL", "app/store.py missing"
    tree = _parse(store)
    if tree is None:
        return "FAIL", "app/store.py does not parse"
    consts = [n.value for n in ast.walk(tree)
              if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    if "STORAGE_PATH" not in set(consts):
        return "FAIL", "STORAGE_PATH not used"
    db_names = {c for c in consts if Path(c).suffix == ".db"}
    if len(db_names) > 1:
        return "FAIL", "multiple db files: " + ", ".join(sorted(db_names))
    # A database opened by a call that names neither the STORAGE_PATH root nor
    # the platform file -- read from the call's own arguments.
    extra_roots = []
    for name, call in _callees(tree):
        args = {n.value for n in ast.walk(call)
                if isinstance(n, ast.Constant) and isinstance(n.value, str)}
        opens_db = name == "sqlite3.connect" or (
            name == "open" and any(Path(a).suffix == ".db" for a in args)
        )
        if opens_db and "STORAGE_PATH" not in args and "platform.db" not in args:
            extra_roots.append(ast.unparse(call))
    if extra_roots:
        return "FAIL", "connect() outside STORAGE_PATH: " + extra_roots[0][:80]
    return "PASS", "one STORAGE_PATH root (%s)" % (next(iter(db_names), "platform.db"))


def check_ci_present_and_full_suite() -> Tuple[str, str]:
    ci = SRC / ".github" / "workflows" / "ci.yml"
    if not ci.is_file():
        return "FAIL", ".github/workflows/ci.yml missing"
    # ci.yml is a Factory-owned file, re-stamped from the Factory's full-suite
    # workflow before every TESTER: the measure is that the product's CI IS
    # that workflow (by digest), never a search of its lines for words.
    raw = ci.read_bytes().replace(b"\r\n", b"\n")
    if hashlib.sha256(raw).hexdigest() == CI_SHA256:
        return "PASS", "CI is the Factory's full-suite workflow (python -m pytest tests)"
    return "FAIL", "ci.yml is not the Factory's full-suite workflow (edited or stale)"


def check_handler_bodies_distinct() -> Tuple[str, str]:
    actions = SRC / "app" / "actions"
    if not actions.is_dir():
        return "FAIL", "app/actions missing"
    bodies: Dict[str, List[str]] = {}
    for path in sorted(actions.glob("*.py")):
        if path.name.startswith("_"):
            continue
        src = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(src)
        except SyntaxError:
            return "FAIL", "%s does not parse" % path.name
        handle = None
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "handle":
                handle = node
                break
        if handle is None:
            continue
        chunk = ast.get_source_segment(src, handle) or ast.dump(handle)
        digest = hashlib.sha256(chunk.encode("utf-8")).hexdigest()
        bodies.setdefault(digest, []).append(path.name)
    twins = [names for names in bodies.values() if len(names) > 1]
    if twins:
        return "FAIL", "identical handle() bodies: " + ", ".join(twins[0])
    if len(bodies) < 2:
        return "PASS", "single handler — nothing to clone"
    return "PASS", "%d distinct handle() bodies" % len(bodies)


#: The DB-API entry points a statement is handed to -- callable NAMES,
#: compared exactly against the call's own target, never searched in text.
_SQL_ENTRY_CALLS = frozenset(
    ("execute", "executemany", "executescript", "exec_driver_sql", "text")
)


def _is_dynamic_string(node, built) -> bool:
    """Built at run time: an f-string with fields, a + or % with a string
    side, a .format() call, or a local name bound to one of those."""
    if isinstance(node, ast.JoinedStr):
        return any(isinstance(v, ast.FormattedValue) for v in node.values)
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Mod)):
        for side in (node.left, node.right):
            if isinstance(side, ast.Constant) and isinstance(side.value, str):
                return True
            if _is_dynamic_string(side, built):
                return True
        return False
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "format"
    ):
        return True
    if isinstance(node, ast.Name):
        return node.id in built
    return False


def _call_target(call) -> str:
    func = call.func
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return ""


def _scope_nodes(scope):
    """Every node of one scope, not descending into nested functions."""
    out = []
    stack = list(ast.iter_child_nodes(scope))
    while stack:
        node = stack.pop()
        out.append(node)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            continue
        stack.extend(ast.iter_child_nodes(node))
    return out


def _dynamic_sql_sites() -> List[str]:
    """file:line of every execute()-family call handed a dynamically built
    string. Decided on the syntax tree: the call's target plus the shape of
    its first argument. Core statements, compiled statements and constant
    literals with bound parameters pass."""
    sites = []
    app_dir = SRC / "app"
    if not app_dir.is_dir():
        return sites
    for path in sorted(app_dir.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except (OSError, SyntaxError):
            continue
        functions = [
            n for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        # A function that hands one of its parameters to an execute call is
        # itself an entry point for that argument position (a writer's own
        # _exec(conn, sql, params) wrapper) -- followed structurally, not by name.
        sinks = dict((name, 0) for name in _SQL_ENTRY_CALLS)
        for _ in range(3):
            for fn in functions:
                params = [a.arg for a in fn.args.args]
                for n in _scope_nodes(fn):
                    if not isinstance(n, ast.Call):
                        continue
                    callee = _call_target(n)
                    position = sinks.get(callee)
                    if position is None or len(n.args) <= position:
                        continue
                    arg = n.args[position]
                    if isinstance(arg, ast.Name) and arg.id in params:
                        sinks.setdefault(fn.name, params.index(arg.id))
        scopes = [tree] + functions
        for scope in scopes:
            nodes = _scope_nodes(scope)
            built = set()
            for _ in range(2):
                for n in nodes:
                    if isinstance(n, ast.Assign) and _is_dynamic_string(n.value, built):
                        built.update(t.id for t in n.targets if isinstance(t, ast.Name))
                    elif (
                        isinstance(n, ast.AugAssign)
                        and isinstance(n.target, ast.Name)
                        and isinstance(n.op, ast.Add)
                    ):
                        built.add(n.target.id)
            for n in nodes:
                if not isinstance(n, ast.Call):
                    continue
                position = sinks.get(_call_target(n))
                if position is None or len(n.args) <= position:
                    continue
                if _is_dynamic_string(n.args[position], built):
                    sites.append("%s:%s" % (path.relative_to(SRC).as_posix(), n.lineno))
    return sorted(set(sites))


def _health_probes_app_db() -> Tuple[bool, str]:
    """app/health.py asks app.db for the live database and runs a probe on
    it -- read from the syntax tree (imports, calls), never from its text."""
    path = SRC / "app" / "health.py"
    if not path.is_file():
        return False, "app/health.py missing"
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError as exc:
        return False, "app/health.py does not parse: %s" % exc
    db_modules = set()
    db_connect = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and n.module == "app":
            for alias in n.names:
                if alias.name == "db":
                    db_modules.add(alias.asname or alias.name)
        elif isinstance(n, ast.ImportFrom) and n.module == "app.db":
            for alias in n.names:
                if alias.name == "connect":
                    db_connect.add(alias.asname or alias.name)
    connects = False
    executes = False
    for n in ast.walk(tree):
        if not isinstance(n, ast.Call):
            continue
        func = n.func
        if isinstance(func, ast.Attribute) and func.attr == "connect":
            if isinstance(func.value, ast.Name) and func.value.id in db_modules:
                connects = True
        if isinstance(func, ast.Name) and func.id in db_connect:
            connects = True
        if isinstance(func, ast.Attribute) and func.attr == "execute":
            executes = True
    if not connects:
        return False, "app/health.py does not take its database connection from app.db"
    if not executes:
        return False, "app/health.py never runs a probe on the database"
    return True, "health probes the database app.db selects"


def check_health_fail_closed() -> Tuple[str, str]:
    probes, why = _health_probes_app_db()
    if not probes:
        return "FAIL", why
    missing = ROOT / ".acceptance-missing-disk"
    previous = os.environ.get("STORAGE_PATH")
    os.environ["STORAGE_PATH"] = str(missing)
    try:
        from app.health import evaluate_health

        code, body = evaluate_health()
    except Exception as exc:
        return "FAIL", "evaluate_health raised %s" % type(exc).__name__
    finally:
        # Restore so later checks (docker_health_200) probe the real disk,
        # not the poisoned path from this fail-closed probe.
        if previous is None:
            os.environ.pop("STORAGE_PATH", None)
        else:
            os.environ["STORAGE_PATH"] = previous
    if code == 200 or (isinstance(body, dict) and body.get("ok") is True):
        return "FAIL", "health stayed 200/ok when STORAGE_PATH is missing"
    if int(code) in (503, 500) and (not body.get("ok")):
        return "PASS", "HTTP %s fail-closed" % code
    return "FAIL", "health code=%s ok=%s" % (code, (body or {}).get("ok"))


def check_migration_no_create_all() -> Tuple[str, str]:
    """Schema belongs to alembic, not to boot.

    create_all() builds tables from whatever the models happen to say at
    start-up, so the migration becomes decoration and the first deploy
    against a real database diverges from what the tests ran on.
    """
    def _calls(tree, attr):
        return [name for name, call in _callees(tree)
                if isinstance(call.func, ast.Attribute) and call.func.attr == attr
                or isinstance(call.func, ast.Name) and call.func.id == attr]

    offenders = []
    for rel in ("app/store.py", "app/main.py", "app/db.py", "app/models.py"):
        tree = _parse(SRC / rel)
        if tree is not None and _calls(tree, "create_all"):
            offenders.append(rel)
    versions = SRC / "alembic" / "versions"
    if not versions.is_dir():
        return "FAIL", "alembic/versions missing: the schema is not migrated"
    revisions = sorted(versions.glob("*.py"))
    if not revisions:
        return "FAIL", "no alembic revision: the schema is not migrated"
    has_ddl = False
    for revision in revisions:
        tree = _parse(revision)
        if tree is None:
            continue
        if _calls(tree, "create_all"):
            offenders.append("alembic/versions/" + revision.name)
        # Real DDL: a call to alembic's op.create_table, resolved by import.
        if any(name.rpartition(".")[0].rpartition(".")[2] == "op"
               for name in _calls(tree, "create_table")):
            has_ddl = True
    if offenders:
        return "FAIL", "create_all in " + ", ".join(sorted(set(offenders)))
    if not has_ddl:
        return "FAIL", "no op.create_table in any revision: not real DDL"
    return "PASS", "%d revision(s), real DDL, no create_all" % len(revisions)


def _capability_stems() -> List[str]:
    actions = SRC / "app" / "actions"
    if not actions.is_dir():
        return []
    return sorted(
        f.stem for f in actions.glob("*.py") if not f.stem.startswith("_")
    )


#: The client-error statuses a counter-case asserts (HTTP 4xx).
NEGATIVE_CODES = frozenset({400, 401, 403, 404, 409, 422, 429})


def _is_4xx(node: ast.AST) -> bool:
    return (isinstance(node, ast.Constant) and isinstance(node.value, int)
            and not isinstance(node.value, bool) and 400 <= node.value < 500)


def _status_compare(node: ast.AST) -> bool:
    """``<x>.status_code == 4xx`` (either side), read from the syntax tree."""
    if not isinstance(node, ast.Compare):
        return False
    sides = [node.left, *node.comparators]
    return any(isinstance(s, ast.Attribute) and s.attr == "status_code" for s in sides) and any(
        _is_4xx(s) for s in sides
    )


def _negative_hits(func: ast.AST) -> int:
    """Count counter-case ASSERTIONS in one test function, from its AST.

    Counting bare 4xx anywhere in a file made a 27KB shared route test hand
    its hits to every capability named in it, and a suite with nine
    counter-cases in total scored four-per-capability. A gate that passes
    what it exists to refuse is worse than no gate. Counted: each
    ``pytest.raises`` context, each ``status_code == 4xx`` comparison, and
    each ``assert`` naming a client-error status without such a comparison.
    """
    alias = _aliases(func)
    hits = 0
    counted = set()
    for node in ast.walk(func):
        if isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                expr = item.context_expr
                if isinstance(expr, ast.Call):
                    head, _, rest = _dotted(expr.func).partition(".")
                    if rest == "raises" and alias.get(head, head) == "pytest":
                        hits += 1
        elif _status_compare(node):
            hits += 1
            counted.add(id(node))
    for node in ast.walk(func):
        if isinstance(node, ast.Assert):
            inner = list(ast.walk(node.test))
            if any(id(n) in counted for n in inner):
                continue
            if any(isinstance(n, ast.Constant) and n.value in NEGATIVE_CODES
                   and not isinstance(n.value, bool) for n in inner):
                hits += 1
    return hits


def check_negative_floor() -> Tuple[str, str]:
    """Four counter-cases per capability, attributed per TEST FUNCTION.

    Attribution is the whole difficulty. Counting hits in any file that
    merely mentions a capability credited every capability with the two big
    shared test files, so a suite with nine counter-cases in total scored
    four-per-capability and passed the gate that exists to refuse it. A
    counter-case counts for a capability only when the test that makes the
    assertion is the test that exercises the capability.
    """
    stems = _capability_stems()
    if not stems:
        return "FAIL", "no app/actions/: nothing to count against"
    tests = SRC / "tests"
    if not tests.is_dir():
        return "FAIL", "no tests/"
    per = dict((stem, 0) for stem in stems)
    for path in sorted(tests.rglob("*.py")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            segment = ast.get_source_segment(text, node) or ""
            if not segment:
                continue
            hits = _negative_hits(node)
            if not hits:
                continue
            for stem in stems:
                if stem in segment or stem in node.name:
                    per[stem] += hits
    thin = ["%s=%d" % (s, per[s]) for s in stems if per[s] < 4]
    if thin:
        return "FAIL", "under 4 counter-cases: " + ", ".join(thin)
    return "PASS", "%d capabilities, each with >=4 counter-cases" % len(stems)


def check_postgres_boot_200(http: _Http) -> Tuple[str, str]:
    """store.py routes through app.db, and DATABASE_URL is actually honoured.

    The old shape of this defect: DATABASE_URL read in the kernel config and
    used nowhere, while store.py held its own sqlite3 handle. The operator
    sets the variable, the platform accepts it without complaint and writes a
    SQLite file onto the container disk. Reading the variable somewhere is
    not the bar; the store taking its connection from one place is.
    """
    db = SRC / "app" / "db.py"
    store = SRC / "app" / "store.py"
    if not db.is_file():
        return "FAIL", "app/db.py missing: nothing decides the backend"
    db_tree = _parse(db)
    if db_tree is None or "DATABASE_URL" not in _env_reads(db_tree):
        return "FAIL", "app/db.py does not read DATABASE_URL"
    if not store.is_file():
        return "FAIL", "app/store.py missing"
    store_tree = _parse(store)
    if store_tree is None:
        return "FAIL", "app/store.py does not parse"
    # From the syntax tree: store.py imports app.db, and opens no database of
    # its own (a resolved sqlite3.connect / create_engine call).
    routes = _imports_module(store_tree, "app.db")
    opens_own = any(
        name == "sqlite3.connect" or name.rpartition(".")[2] == "create_engine"
        for name, _call in _callees(store_tree)
    )
    if not routes:
        return (
            "FAIL",
            "app/store.py does not take its connection from app.db, so a set "
            "DATABASE_URL is read and ignored",
        )
    if opens_own:
        return (
            "FAIL",
            "app/store.py opens its own database beside app.db; one place must "
            "decide the backend or the two disagree",
        )
    unmeasured = _only_the_gate_measures("STORE_POSTGRES_BOOT")
    if unmeasured is not None:
        return unmeasured
    measured = (os.environ.get("STORE_POSTGRES_BOOT") or "").strip()
    if measured != "200":
        return "FAIL", "STORE_POSTGRES_BOOT=%r (gate must boot it on Postgres)" % measured
    resp = http.request("get", "/health")
    if resp.status_code != 200:
        return "FAIL", "postgres boot env=200 but /health is %s" % resp.status_code
    return "PASS", "store.py routes through app.db; boots on Postgres"


def check_one_live_connector() -> Tuple[str, str]:
    measured = (os.environ.get("STORE_LIVE_CONNECTOR") or "").strip()
    if not measured:
        return "FAIL", "STORE_LIVE_CONNECTOR unset: no real delivery was observed"
    if measured.lower() in ("0", "false", "mocked", "no"):
        return "FAIL", "the only observed delivery was mocked (%s)" % measured
    return "PASS", "live delivery observed: %s" % measured


def check_metrics_served(http: _Http) -> Tuple[str, str]:
    """Measured on the booted app. Shipping the module is not mounting it."""
    resp = http.request("get", "/metrics")
    if resp.status_code != 200:
        mounted = "mount_observability" in (
            (SRC / "app" / "main.py").read_text(encoding="utf-8", errors="ignore")
            if (SRC / "app" / "main.py").is_file()
            else ""
        )
        hint = (
            "app/main.py never calls mount_observability(app)"
            if not mounted
            else "mount_observability is called but /metrics does not answer"
        )
        return "FAIL", "GET /metrics is %s -- %s" % (resp.status_code, hint)
    try:
        body = resp.text
    except Exception:
        body = ""
    low = body.lower()
    if not any(k in low for k in ("count", "total", "requests")):
        return "FAIL", "/metrics answers 200 but reports no request count"
    if not any(k in low for k in ("latency", "duration", "seconds")):
        return "FAIL", "/metrics reports no latency"
    return "PASS", "/metrics serves a request count and latency"


def check_backup_restore_roundtrip() -> Tuple[str, str]:
    measured = (os.environ.get("STORE_BACKUP_RESTORE") or "").strip().lower()
    if measured in ("ok", "pass", "1", "true"):
        return "PASS", "backup restored with rows intact"
    if not (SRC / "app" / "backup.py").is_file():
        return "FAIL", "no app/backup.py"
    return "FAIL", "STORE_BACKUP_RESTORE=%r: a backup nobody restored is a file" % measured


def check_bench_p95() -> Tuple[str, str]:
    measured = (os.environ.get("STORE_BENCH_P95_MS") or "").strip()
    if not measured:
        return "FAIL", "STORE_BENCH_P95_MS unset: p95 was not measured"
    try:
        value = float(measured)
    except ValueError:
        return "FAIL", "STORE_BENCH_P95_MS=%r is not a number" % measured
    if value >= 500.0:
        return "FAIL", "p95 %.0fms over the 500ms budget" % value
    return "PASS", "p95 %.0fms under 500ms" % value


def check_audit_clean() -> Tuple[str, str]:
    ci = SRC / ".github" / "workflows" / "ci.yml"
    if not ci.is_file():
        return "FAIL", ".github/workflows/ci.yml missing"
    text = ci.read_text(encoding="utf-8", errors="ignore").lower()
    missing = [t for t in ("pip-audit", "bandit") if t not in text]
    if missing:
        return "FAIL", "CI does not run " + ", ".join(missing)
    dynamic = _dynamic_sql_sites()
    if dynamic:
        return "FAIL", "dynamically built SQL reaches an execute call: " + ", ".join(dynamic[:6])
    unmeasured = _only_the_gate_measures("STORE_AUDIT_CLEAN")
    if unmeasured is not None:
        return unmeasured
    measured = (os.environ.get("STORE_AUDIT_CLEAN") or "").strip().lower()
    if measured in ("0", "false", "dirty"):
        return "FAIL", "bandit/pip-audit reported HIGH or SQL-construction findings"
    if measured not in ("1", "true", "clean"):
        # F3: a scan that is CONFIGURED but never RUN is not a pass. A product
        # shipped 16 bandit SQL findings and still scored 21/21 because this
        # check only proved ci.yml mentions the scanners. The store gate must
        # RUN the scan and export STORE_AUDIT_CLEAN, exactly as it measures
        # STORE_POSTGRES_BOOT -- unmeasured is a fail, never a silent pass.
        return "FAIL", "STORE_AUDIT_CLEAN unmeasured: the gate must run bandit/pip-audit and read the verdict, not just confirm the scan is configured"
    return "PASS", "scan ran and is clean (no HIGH, no SQL-construction findings)"


def check_no_token_literal() -> Tuple[str, str]:
    """Runtime app/** carries no baked bearer token and no token fallback.

    The well-known dev values live in the TEST bootstrap (tests/conftest.py)
    only; the deploy env carries a per-package random token. A baked token is
    a production backdoor -- live 2026-09-29, a second-tenant token literal
    opened another tenant on a CERTIFIED product with a world-known value.
    An EMPTY default (or two quotes with nothing between) is the fail-closed
    pattern and is allowed.
    """
    app_dir = SRC / "app"
    if not app_dir.is_dir():
        return "FAIL", "app/ missing"
    # The world-known development token values (the test bootstrap's), as
    # exact constants -- a value comparison, not a search of text.
    literals = frozenset({"dev-local-token-b", "dev-local-token"})
    readers = {"os.environ.get", "os.getenv"}

    def _token_read(node: ast.AST, calls: Dict[int, str]) -> bool:
        return (isinstance(node, ast.Call) and calls.get(id(node)) in readers
                and bool(node.args) and isinstance(node.args[0], ast.Constant)
                and node.args[0].value == "PLATFORM_TOKEN")

    def _nonempty_str(node: ast.AST) -> bool:
        return isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value != ""

    for path in sorted(app_dir.rglob("*.py")):
        tree = _parse(path)
        if tree is None:
            continue
        rel = path.relative_to(SRC)
        calls = {id(call): name for name, call in _callees(tree)}
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and node.value in literals:
                return "FAIL", "%s:%s bakes %s -- runtime tokens come from the environment only" % (rel, node.lineno, node.value)
            if _token_read(node, calls) and len(node.args) > 1 and _nonempty_str(node.args[1]):
                return "FAIL", "%s:%s has a token default -- read the environment and fail closed instead" % (rel, node.lineno)
            if (isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or)
                    and any(_token_read(v, calls) for v in node.values)
                    and any(_nonempty_str(v) for v in node.values)):
                return "FAIL", "%s:%s has an env-fallback token -- read the environment and fail closed instead" % (rel, node.lineno)
    return "PASS", "no token literal or fallback in runtime app/**"


def check_openapi_committed() -> Tuple[str, str]:
    path = SRC / "docs" / "openapi.json"
    if not path.is_file():
        return "FAIL", "docs/openapi.json missing"
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return "FAIL", "openapi is not JSON: %s" % exc
    if not str(doc.get("openapi") or "").startswith("3."):
        return "FAIL", "openapi version is not 3.x"
    paths = doc.get("paths")
    if not isinstance(paths, dict) or "/health" not in paths:
        return "FAIL", "openapi paths omit /health"
    v1 = [p for p in paths if str(p).startswith("/v1/")]
    if not v1:
        return "FAIL", "openapi has no /v1/ paths"
    return "PASS", "openapi 3.x with %d paths" % len(paths)


#: Advice only, appended to the self-check's SKIP reason: the image is measured
#: by the Store gate alone, but the writer may build it itself to catch a
#: Dockerfile that cannot build before the gate does.
IMAGE_BUILD_ADVICE = (
    "; build it yourself with `docker build .` -- the Dockerfile must build "
    "without dev dependencies or running the test suite"
)


def check_docker_health_200(http: _Http) -> Tuple[str, str]:
    unmeasured = _only_the_gate_measures("STORE_DOCKER_HEALTH")
    if unmeasured is not None:
        status, reason = unmeasured
        return status, reason + IMAGE_BUILD_ADVICE
    measured = (os.environ.get("STORE_DOCKER_HEALTH") or "").strip()
    if measured != "200":
        return "FAIL", "STORE_DOCKER_HEALTH=%r (Store gate must measure container /health=200)" % measured
    resp = http.request("get", "/health")
    if resp.status_code != 200:
        return "FAIL", "container health env=200 but GET /health is %s" % resp.status_code
    return "PASS", "docker health 200"


import dataclasses as _dataclasses
import json as _json

_SAMPLE_BY_TYPE = {'str': 'sample', 'int': 1, 'float': 1.5, 'bool': True}
_ACCEPT_STATUSES = (200,)
_OK_KEY = 'ok'


def _model_of(capability_id):
    try:
        from app.models import MODELS
    except Exception:
        return None
    return MODELS.get(capability_id)


def _field_sample(capability_id, field):
    """A value the product's own model declares acceptable for ``field``."""
    cls = _model_of(capability_id)
    if cls is None:
        return None
    rules = (getattr(cls, 'CONSTRAINTS', {}) or {}).get(field) or {}
    allowed = rules.get('allowed_values')
    if allowed:
        return allowed[0]
    default = None
    if _dataclasses.is_dataclass(cls):
        attr = (getattr(cls, '_FIELD_PY', {}) or {}).get(field, field)
        for f in _dataclasses.fields(cls):
            if f.name != attr:
                continue
            if f.default is not _dataclasses.MISSING:
                default = f.default
            elif f.default_factory is not _dataclasses.MISSING:
                default = f.default_factory()
    low = rules.get('min')
    if default not in (None, '') and not isinstance(default, bool):
        if not isinstance(default, (int, float)) or default:
            if low is None or not isinstance(default, (int, float)) or default >= low:
                return default
    sample = _SAMPLE_BY_TYPE.get(type(default).__name__, _SAMPLE_BY_TYPE['str'])
    if low is not None and isinstance(sample, (int, float)) and sample < low:
        sample = low
    return sample


def _sample_payload_for(capability_id, base):
    """The Factory spec sample, completed with every field the product's
    own model declares required and the sample lacks."""
    payload = dict(base or {})
    cls = _model_of(capability_id)
    if cls is None:
        return payload
    constraints = getattr(cls, 'CONSTRAINTS', {}) or {}
    for name in list(getattr(cls, 'FIELDS', []) or []):
        if not (constraints.get(name) or {}).get('required'):
            continue
        if payload.get(name) in (None, ''):
            value = _field_sample(capability_id, name)
            if value not in (None, ''):
                payload[name] = value
    return payload


def _rejection(resp):
    """The rejection as data: (field, reason, allowed) or None. Read from
    the structured rejection the product states -- headers on a 422,
    keys on an ok:false body -- never from prose or JSON text, so no
    token in a response body can leak into a payload."""
    field = resp.headers.get('X-Rejected-Field')
    if field is not None:
        try:
            field = _json.loads(field)
        except ValueError:
            return None
        reason = resp.headers.get('X-Rejection-Reason')
        allowed = resp.headers.get('X-Allowed-Values')
        try:
            allowed = _json.loads(allowed) if allowed is not None else None
        except ValueError:
            allowed = None
        return field, reason, allowed
    try:
        body = resp.json()
    except Exception:
        return None
    if not isinstance(body, dict) or 'rejected_field' not in body:
        return None
    return (body.get('rejected_field'), body.get('rejection_reason'),
            body.get('allowed_values'))


def _post_accepting(path, payload, headers, capability_id=None):
    """POST the completed payload; when the product refuses a field AS
    DATA, adopt the value its own model declares and retry. Returns
    (response, corrections). Each (field, value) is tried at most once,
    so the loop converges or stops. A refusal that is not a field
    rejection (a 503 placeholder refusal, a 401) is returned as is."""
    payload = _sample_payload_for(capability_id, payload)
    corrections = []
    tried = set()
    resp = client.post(path, json=payload, headers=headers)
    for _ in range(len(payload) + 2):
        failed = resp.status_code not in _ACCEPT_STATUSES
        if not failed:
            try:
                failed = resp.json().get(_OK_KEY) is False
            except Exception:
                failed = False
        if not failed:
            break
        rejection = _rejection(resp)
        if rejection is None:
            break
        field, reason, allowed = rejection
        if not isinstance(field, str) or not field:
            break
        if reason == 'not_allowed' and isinstance(allowed, list) and allowed:
            value = allowed[0]
        elif reason == 'missing_required':
            value = _field_sample(capability_id, field)
            if value in (None, ''):
                break
        else:
            break
        key = (field, repr(value))
        if key in tried:
            break
        tried.add(key)
        corrections.append(
            str(field) + '=' + repr(payload.get(field)) + '->' + repr(value)
        )
        payload[field] = value
        resp = client.post(path, json=payload, headers=headers)
    if _still_failed(resp):
        _record_capability_failure(capability_id)
    return resp, corrections


def _still_failed(resp):
    if resp.status_code not in _ACCEPT_STATUSES:
        return True
    try:
        return resp.json().get(_OK_KEY) is False
    except Exception:
        return False


import json as _cap_json
import os as _cap_os


def _record_capability_failure(capability_id):
    """Factory suite only: note the capability this running test found
    failing (pytest names the test in PYTEST_CURRENT_TEST)."""
    path = _cap_os.environ.get('FACTORY_CAPABILITY_LOG')
    if not path or not capability_id:
        return
    running = _cap_os.environ.get("PYTEST_CURRENT_TEST") or ""
    test = running.rsplit(" (", 1)[0]
    try:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(_cap_json.dumps({"test": test, "capability": str(capability_id)}) + "\n")
    except OSError:
        pass

_ENTITY_UNDECLARED = object()
DEFAULT_TENANT = 'local'


def _jobs_entities():
    try:
        from app.jobs import CAPABILITIES
    except Exception:
        return {}
    out = {}
    for item in CAPABILITIES or []:
        if isinstance(item, dict) and item.get("id") and "entity" in item:
            out[item["id"]] = item.get("entity")
    return out


_JOBS_ENTITIES = _jobs_entities()


def _route_entities():
    try:
        from app.routes import ROUTE_ENTITIES
    except Exception:
        return {}
    return dict(ROUTE_ENTITIES or {})


_ROUTE_ENTITIES = _route_entities()


def _declared_entity(cap_id, cls):
    """(entity, declared). entity None/'' with declared=True: persists nothing.

    The Factory-rendered route's save target comes first (every product
    built through the Factory carries it); then the capability manifest
    (app.jobs.CAPABILITIES); then the handler module's ENTITY; then the model.
    """
    import importlib
    if cap_id in _ROUTE_ENTITIES:
        return _ROUTE_ENTITIES[cap_id], True
    if cap_id in _JOBS_ENTITIES:
        return _JOBS_ENTITIES[cap_id], True
    module_name = "app.actions." + str(cap_id).replace("-", "_")
    try:
        module = importlib.import_module(module_name)
    except Exception:
        module = None
    if module is not None and hasattr(module, "ENTITY"):
        return getattr(module, "ENTITY"), True
    if hasattr(cls, "ENTITY"):
        return getattr(cls, "ENTITY"), True
    return None, False


_PROBE_TENANT = []


def _probe_tenant():
    """The tenant the route wrote under, resolved lazily (AUTH may be bound
    after this source in the probe)."""
    if not _PROBE_TENANT:
        tenant_id = None
        try:
            from app.tenancy import resolve_tenant
            tenant_id = resolve_tenant(AUTH).tenant_id
        except Exception:
            tenant_id = None
        _PROBE_TENANT.append(tenant_id)
    return _PROBE_TENANT[0]


def _list_entity(entity):
    tenant_id = _probe_tenant()
    if tenant_id is None:
        # No tenancy module to ask: a single-tenant product, whose one tenant
        # is the default the Factory's tenancy module declares.
        tenant_id = DEFAULT_TENANT
    try:
        return store.list_all(entity, tenant_id=tenant_id)
    except TypeError:
        # A store that is not tenant-scoped at all.
        return store.list_all(entity)


class _CreateClient:
    """The shared payload builder posts through a module-level ``client``;
    in the harness that is the harness's own HTTP client."""

    def __init__(self, http: _Http):
        self.http = http

    def post(self, path, json=None, headers=None):
        return self.http.request("post", path, json=json, headers=headers)


def _persisting_caps() -> List[str]:
    """Capabilities that DECLARE a persisted entity -- read by the same
    resolver as the round-trip probes, never assumed from the capability id --
    minus declared placeholders, in capability order. A read-only capability
    (declared entity None) and an undeclared one are not creatable here."""
    try:
        from app.placeholders import PLACEHOLDER_CONNECTORS
    except Exception:
        PLACEHOLDER_CONNECTORS = {}
    # The resolver reads the declarations once at import; read them again
    # now that the harness has its environment, so a route module that could
    # not import earlier is not mistaken for "declares nothing".
    globals()["_ROUTE_ENTITIES"] = _route_entities()
    globals()["_JOBS_ENTITIES"] = _jobs_entities()
    models = _models()
    out = []
    for cap in _cap_order():
        if PLACEHOLDER_CONNECTORS.get(cap):
            continue
        entity, declared = _declared_entity(cap, models.get(cap))
        if declared and entity:
            out.append(cap)
    return out


def _created_id(resp: Any) -> Tuple[Any, str]:
    """(record id, refusal) read by the route's create contract. HTTP 200
    with 'ok': false is a refusal, never a success."""
    try:
        body = resp.json()
    except Exception:
        body = None
    if resp.status_code not in (200,):
        detail = body.get('error') if isinstance(body, dict) else ""
        return None, "HTTP %s %s" % (resp.status_code, detail or "")
    if not isinstance(body, dict):
        return None, "answered no JSON object"
    if body.get('ok') is False:
        return None, "refused: %s" % (body.get('error') or 'ok' + ": false")
    record = body.get('stored')
    if not isinstance(record, dict) or record.get('id') in (None, ""):
        return None, "accepted but answered no %s.%s" % ('stored', 'id')
    return record.get('id'), ""


def check_cross_tenant_404(http: _Http) -> Tuple[str, str]:
    """Write as tenant A, read as tenant B: the read must be 404.

    404-not-403 is the platform's stated doctrine -- cross-tenant access
    never leaks existence. A 200/403 here means the product is
    single-tenant by construction (the Phase-2 0.2 defect).

    The record is created through a capability that DECLARES a persisted
    entity, with the shared payload builder every emitted suite uses (the
    product's own model fills required fields; a rejection stated as data is
    corrected once). A refused create is reported with the product's own
    refusal as evidence -- never as "no stored id".
    """
    previous = os.environ.get("TENANT_TOKENS")
    os.environ["TENANT_TOKENS"] = CHECK_TENANT_TOKENS
    try:
        caps = _persisting_caps()
        if not caps:
            return "SKIP", (
                "no capability declares a persisted entity -- isolation needs a "
                "stored record, so it is not judgeable on this product"
            )
        globals()["client"] = _CreateClient(http)
        refusals = []
        for cap in caps:
            resp, _corrections = _post_accepting(
                "/v1/" + cap, {}, {"Authorization": "Bearer token-a"}, cap,
            )
            record_id, refusal = _created_id(resp)
            if record_id is None:
                refusals.append("%s: %s" % (cap, refusal))
                continue
            read = http.request(
                "get", "/v1/%s/%s" % (cap, record_id),
                headers={"Authorization": "Bearer token-b"},
            )
            if read.status_code == 404:
                return "PASS", "tenant B read of tenant A %s record: HTTP 404" % cap
            return "FAIL", "tenant B read of tenant A %s record returned HTTP %s (want 404)" % (cap, read.status_code)
        return "FAIL", (
            "tenant A could not store a record through any capability that "
            "declares a persisted entity -- " + "; ".join(refusals)
        )[:700]
    finally:
        if previous is None:
            os.environ.pop("TENANT_TOKENS", None)
        else:
            os.environ["TENANT_TOKENS"] = previous



CONCURRENCY_POOL_FACTOR = 2
CONCURRENCY_DEFAULT_POOL_CAPACITY = 15
CONCURRENCY_TIMEOUT_S = 120


def _pool_capacity() -> Tuple[Optional[int], str]:
    """(pool_size + max_overflow, where it was read). None when unbounded or
    unreadable. Read off the engine the product's own app.db builds -- the
    one place that decides the backend -- never from its source text."""
    try:
        import app.db as _db
    except Exception as exc:
        return None, "app.db not importable (%s)" % type(exc).__name__
    eng = getattr(_db, "engine", None)
    if callable(eng) and not hasattr(eng, "pool"):
        try:
            eng = eng()
        except Exception as exc:
            return None, "app.db.engine() raised %s" % type(exc).__name__
    pool = getattr(eng, "pool", None)
    size = getattr(pool, "size", None)
    overflow = getattr(pool, "_max_overflow", None)
    if callable(size) and isinstance(overflow, int) and overflow >= 0:
        try:
            pool_size = int(size())
        except Exception:
            return None, "the engine's pool size is unreadable"
        return pool_size + overflow, "app.db pool_size=%d + max_overflow=%d" % (pool_size, overflow)
    if pool is None:
        return None, "app.db exposes no engine pool"
    return None, "app.db's %s has no bounded size" % type(pool).__name__


def _library_pool_capacity() -> Tuple[int, str]:
    """The pool library's own defaults, read from the copy the product
    loaded (never imported here: the harness is standard library only)."""
    import inspect

    module = sys.modules.get("sqlalchemy.pool")
    queue_pool = getattr(module, "QueuePool", None)
    if queue_pool is not None:
        try:
            params = inspect.signature(queue_pool.__init__).parameters
            size = int(params["pool_size"].default)
            overflow = int(params["max_overflow"].default)
            return size + overflow, "the loaded pool library's default %d + %d" % (size, overflow)
        except Exception:
            pass
    return CONCURRENCY_DEFAULT_POOL_CAPACITY, "the default pool capacity %d" % CONCURRENCY_DEFAULT_POOL_CAPACITY


def _declared_threadpool() -> Tuple[int, str]:
    """The widest sync threadpool the product declares or its runtime runs:
    app.store.FASTAPI_SYNC_THREADPOOL, the durability record in
    docs/data_lifecycle.json, and the loaded anyio's default thread limiter
    (the pool FastAPI runs sync routes on)."""
    found = []
    try:
        import app.store as _store

        value = getattr(_store, "FASTAPI_SYNC_THREADPOOL", None)
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            found.append((value, "app.store.FASTAPI_SYNC_THREADPOOL"))
    except Exception:
        pass
    for base in (ROOT, REPO):
        path = base / "docs" / "data_lifecycle.json"
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        value = ((record or {}).get("durability") or {}).get("fastapi_sync_threadpool")
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            found.append((value, "docs/data_lifecycle.json"))
        break
    anyio = sys.modules.get("anyio")
    if anyio is not None:
        try:
            async def _tokens():
                return anyio.to_thread.current_default_thread_limiter().total_tokens

            value = int(anyio.run(_tokens))
            if value > 0:
                found.append((value, "the runtime's sync thread limiter"))
        except Exception:
            pass
    if not found:
        return 0, "no declared threadpool"
    return max(found)


def _concurrency_width() -> Tuple[int, str]:
    """N, and how it was derived: POOL_FACTOR x the pool capacity, never
    fewer than the sync threadpool."""
    capacity, source = _pool_capacity()
    if capacity is None:
        why = source
        capacity, source = _library_pool_capacity()
        source = "%s (%s)" % (source, why)
    threads, thread_source = _declared_threadpool()
    width = max(CONCURRENCY_POOL_FACTOR * capacity, threads, 2)
    return width, "N=%d: %dx pool %d [%s]; sync threadpool %d [%s]" % (
        width, CONCURRENCY_POOL_FACTOR, capacity, source, threads, thread_source,
    )


def _at_once(fn, n: int) -> List[Tuple[bool, Any]]:
    """Run fn(0..n-1) on n threads released together. (ok, value or error)
    per call; a call still running at the deadline is an unanswered write."""
    import threading
    import time

    gate = threading.Barrier(n)
    results: List[Any] = [None] * n

    def _one(i: int) -> None:
        try:
            gate.wait(timeout=CONCURRENCY_TIMEOUT_S)
        except threading.BrokenBarrierError:
            pass
        try:
            results[i] = (True, fn(i))
        except Exception as exc:
            results[i] = (False, "%s: %s" % (type(exc).__name__, exc))

    threads = [threading.Thread(target=_one, args=(i,), daemon=True) for i in range(n)]
    for thread in threads:
        thread.start()
    deadline = time.monotonic() + CONCURRENCY_TIMEOUT_S
    for thread in threads:
        thread.join(max(0.0, deadline - time.monotonic()))
    return [
        r if r is not None else (False, "no answer within %ss" % CONCURRENCY_TIMEOUT_S)
        for r in results
    ]


def _first_error(errors: List[str]) -> str:
    return (errors[0] if errors else "")[:300]


class _CapturingClient(_CreateClient):
    """The harness client that remembers the last body it posted: the
    payload the product accepted, after the shared builder's corrections."""

    def __init__(self, http: _Http):
        super().__init__(http)
        self.sent = None

    def post(self, path, json=None, headers=None):
        self.sent = dict(json or {})
        return super().post(path, json=json, headers=headers)


def _http_leg(http: _Http, path: str, payload: Dict[str, Any], headers: Dict[str, str], n: int) -> str:
    """N creates through the served route at once. '' when every one is
    accepted with its own stored id and reads back; else why not."""

    def _create(_i: int):
        resp = http.request("post", path, json=dict(payload), headers=headers, timeout=CONCURRENCY_TIMEOUT_S)
        record_id, refusal = _created_id(resp)
        if record_id is None:
            raise RuntimeError(refusal or "no stored id")
        return record_id

    outcomes = _at_once(_create, n)
    errors = [str(v) for ok, v in outcomes if not ok]
    if errors:
        return "%d of %d concurrent creates failed; first error: %s" % (len(errors), n, _first_error(errors))
    ids = [v for _ok, v in outcomes]
    distinct = {str(i) for i in ids}
    if len(distinct) != n:
        return "%d concurrent creates answered success but only %d distinct stored ids" % (n, len(distinct))
    for record_id in ids:
        read = http.request("get", "%s/%s" % (path, record_id), headers=headers, timeout=CONCURRENCY_TIMEOUT_S)
        if read.status_code != 200:
            return "created id %s reads back HTTP %s (want 200): %d accepted, not all stored" % (
                record_id, read.status_code, n,
            )
    return ""


def _store_leg(entity: str, payload: Dict[str, Any], tenant_id: str, n: int) -> str:
    """N calls of the store's declared write at once, from N threads.
    '' when every one returns its stored record and all N are counted."""
    try:
        import app.store as _store
    except Exception as exc:
        return "app.store does not import: %s: %s" % (type(exc).__name__, exc)
    save = getattr(_store, "save", None)
    if not callable(save):
        return "app.store declares no save(entity, record, tenant_id=)"
    list_all = getattr(_store, "list_all", None)

    def _count() -> Optional[int]:
        if not callable(list_all):
            return None
        try:
            return len(list_all(entity, tenant_id=tenant_id))
        except Exception:
            return None

    before = _count()
    outcomes = _at_once(lambda _i: save(entity, dict(payload), tenant_id=tenant_id), n)
    errors = [str(v) for ok, v in outcomes if not ok]
    if errors:
        return "%d of %d concurrent saves failed; first error: %s" % (len(errors), n, _first_error(errors))
    ids = [v.get('id') if isinstance(v, dict) else None for _ok, v in outcomes]
    if all(i not in (None, "") for i in ids) and len({str(i) for i in ids}) != n:
        return "%d concurrent saves returned only %d distinct ids" % (n, len({str(i) for i in ids}))
    after = _count()
    if before is not None and after is not None and after - before != n:
        return "%d concurrent saves returned, but the store holds %d more" % (n, after - before)
    return ""


def check_concurrent_writes_hold(http: _Http) -> Tuple[str, str]:
    """Every write path takes N simultaneous creates: N = 2x the product's
    pool capacity, never fewer than its sync threadpool. A store that holds
    a pooled connection while it checks out another (save() calling get()
    on a fresh connection) deadlocks here and times out."""
    caps = _persisting_caps()
    if not caps:
        return "SKIP", (
            "no capability declares a persisted entity -- there is no write "
            "path to drive concurrently on this product"
        )
    n, derivation = _concurrency_width()
    token, _, tenant_id = CHECK_TENANT_TOKENS.split(",")[0].partition(":")
    headers = {"Authorization": "Bearer " + token}
    capture = _CapturingClient(http)
    globals()["client"] = capture
    models = _models()
    judged, refused = [], []
    for cap in caps:
        path = "/v1/" + cap
        capture.sent = None
        resp, _corrections = _post_accepting(path, {}, headers, cap)
        record_id, refusal = _created_id(resp)
        if record_id is None:
            # Not a write path this product can take a single create on:
            # cross_tenant_404 and the round-trip judge that. Here it is
            # reported, never driven.
            refused.append("%s: %s" % (cap, refusal))
            continue
        payload = dict(capture.sent or {})
        problem = _http_leg(http, path, payload, headers, n)
        if problem:
            return "FAIL", ("POST %s at N=%d: %s (%s)" % (path, n, problem, derivation))[:900]
        entity, _declared = _declared_entity(cap, models.get(cap))
        problem = _store_leg(str(entity), payload, tenant_id, n)
        if problem:
            return "FAIL", (
                "app.store.save(%r) at N=%d (the write behind POST %s): %s (%s)"
                % (entity, n, path, problem, derivation)
            )[:900]
        judged.append(cap)
    if not judged:
        return "FAIL", (
            "no write path accepted a single create, so none could be driven "
            "concurrently -- " + "; ".join(refused)
        )[:900]
    note = ("; not driven (refused a single create): " + "; ".join(refused)) if refused else ""
    return "PASS", (
        "%d write path(s) x %d concurrent creates, HTTP and store: every one "
        "accepted with its own id and stored (%s)%s" % (len(judged), n, derivation, note)
    )[:900]


def _authored_by(text):
    import ast as _ast
    try:
        tree = _ast.parse(text or "")
    except (SyntaxError, ValueError):
        return ""
    for node in tree.body:
        if isinstance(node, _ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, _ast.AnnAssign):
            targets, value = [node.target], node.value
        else:
            continue
        if any(isinstance(t, _ast.Name) and t.id == 'AUTHORED_BY' for t in targets):
            if isinstance(value, _ast.Constant) and isinstance(value.value, str):
                return value.value.strip()
    return ""


def check_authorship_floor() -> Tuple[str, str]:
    # Judge the product by the product. Each handler's module-level
    # authorship marker, read from the syntax tree by a reader RENDERED in
    # here from the Factory's canonical one (with its source vocabulary) at
    # stamp time: a delivered product never carries the Factory package, and
    # importing it failed this line on every honest build (2026-10-04). A
    # docstring sentence decides nothing.
    agent_prefixes = ('coder LLM', 'coder CLI', 'FACTORY_CODE_CLI', 'codewhale')
    agent_exact = ['compiled-brief oneshot', 'harvested workspace handler']
    floor_min = 5
    receipt = {}
    for rel in ("docs/coder_receipt.json", "docs/build_provenance.json"):
        path = SRC / rel
        if path.is_file():
            try:
                receipt.update(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                pass
    actions = SRC / "app" / "actions"
    authored = 0
    for path in (sorted(actions.glob("*.py")) if actions.is_dir() else []):
        try:
            source = _authored_by(path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        if source and (source.startswith(tuple(agent_prefixes)) or source.lower() in agent_exact):
            authored += 1
    n_required = receipt.get("n_required") or receipt.get("n_required_capabilities")
    try:
        n_required = int(n_required) if n_required is not None else None
    except (TypeError, ValueError):
        n_required = None
    need = floor_min if not n_required or n_required <= 0 else min(floor_min, max(1, n_required))
    if authored >= need:
        return "PASS", "authored=%s need≥%s" % (authored, need)
    return "FAIL", "authored=%s below need≥%s" % (authored, need)


DEPLOY_TIME_PLACEHOLDER = "set-at-deploy"


def _stand_in_for_deploy_time_settings(root):
    """Give every setting the product REQUIRES, and the build cannot have, a
    stand-in -- so importing the product does not KeyError on a credential its
    operator supplies at deploy time. Returns the names stood in for."""
    import ast as _ast
    import os as _os
    from pathlib import Path as _Path

    root = _Path(root)
    examples = {}
    env_example = root / ".env.example"
    if env_example.is_file():
        for raw in env_example.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            value = value.split(" #", 1)[0].strip().strip("'\"")
            if key.strip():
                examples[key.strip()] = value

    def _is_environ(node):
        if isinstance(node, _ast.Attribute) and node.attr == "environ":
            return isinstance(node.value, _ast.Name) and node.value.id == "os"
        return isinstance(node, _ast.Name) and node.id == "environ"

    required = set()
    app_dir = root / "app"
    if app_dir.is_dir():
        for path in app_dir.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            try:
                tree = _ast.parse(path.read_text(encoding="utf-8", errors="replace"))
            except (SyntaxError, ValueError):
                continue
            for node in _ast.walk(tree):
                if (
                    isinstance(node, _ast.Subscript)
                    and isinstance(node.ctx, _ast.Load)
                    and _is_environ(node.value)
                    and isinstance(node.slice, _ast.Constant)
                    and isinstance(node.slice.value, str)
                ):
                    required.add(node.slice.value)

    stood_in = []
    for name in sorted(required):
        if name not in _os.environ:
            _os.environ[name] = examples.get(name) or DEPLOY_TIME_PLACEHOLDER
            stood_in.append(name)
    return stood_in


def main() -> int:
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    # Before anything imports ``app``: a credential the operator supplies at
    # deploy time must not fail acceptance on the build box. Shared, word for
    # word, with tests/conftest.py.
    _stand_in_for_deploy_time_settings(ROOT)
    http, cm = _client()
    results: List[Tuple[str, str, str]] = []
    try:
        # Generated from the floor, not written out here. A hand-kept list
        # is the second copy the floor file exists to abolish: it drifts the
        # moment a check is added, and the build is then graded against a
        # roster nobody updated. Order is the floor's order.
        import inspect as _inspect

        runners = []
        for _name in CHECKS:
            _fn = globals().get("check_" + _name)
            if _fn is None:
                runners.append(
                    (_name, (lambda n=_name: ("FAIL", "no check_%s in the harness" % n)))
                )
                continue
            if "http" in _inspect.signature(_fn).parameters:
                runners.append((_name, (lambda f=_fn: f(http))))
            else:
                runners.append((_name, _fn))
        global SRC
        for name, fn in runners:
            SRC = REPO if name in REPO_CHECKS else ROOT
            try:
                status, detail = fn()
            except Exception as exc:
                status, detail = "FAIL", "%s: %s" % (type(exc).__name__, exc)
            if status == "FAIL" and name in ADVISORY:
                status, detail = "SKIP", "advisory (not on the floor yet): " + detail
            results.append((name, status, detail))
            print("%s %s — %s" % (status, name, detail))
            # The typed record the Factory reads; the line above is for people.
            print(json.dumps({RECORD_KEY: {"name": name, "status": status, "detail": detail}}))
    finally:
        if cm is not None:
            try:
                cm.__exit__(None, None, None)
            except Exception:
                pass
    satisfied = sum(1 for _n, status, _d in results if status in {"PASS", "SKIP"})
    print("ACCEPTANCE: %d/%d" % (satisfied, REQUIRED))
    if SELF_CHECK:
        print("SELF-CHECK: the same %d checks the Store gate scores; fix every FAIL before you declare done" % REQUIRED)
    print(json.dumps({TOTAL_KEY: {"passed": satisfied, "required": REQUIRED}}))
    if results and results[-1][0] != "authorship_floor":
        print("FAIL harness — authorship_floor was not last")
        return 1
    if satisfied < REQUIRED or any(status == "FAIL" for _n, status, _d in results):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
