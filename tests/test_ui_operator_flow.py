"""The served UI reaches the product -- the same bar ui_end_to_end holds.

Run before you yield. A failure here is a failure the gate would have found
after you yielded, at the cost of a full rework round.
"""

from __future__ import annotations

import ast
import json
import os
import re
from pathlib import Path

import pytest


def _imports_formulas(path):
    """The handler imports the product's formulas module (syntax tree)."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(a.name.split(".")[-1] == "formulas" for a in node.names):
            return True
        if isinstance(node, ast.ImportFrom):
            if (node.module or "").split(".")[-1] == "formulas" or any(a.name == "formulas" for a in node.names):
                return True
    return False


def _dockerfile_builds(directory):
    """The Dockerfile, read as instructions: the image builds ``directory``
    when a COPY/ADD brings it in (or a WORKDIR enters it) and a RUN follows."""
    path = Path("Dockerfile")
    if not path.is_file():
        return False
    entered = False
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line[0] == "#":
            continue
        keyword, _, rest = line.partition(" ")
        keyword = keyword.upper()
        args = [a for a in rest.split() if a[:2] != "--"]
        if keyword in ("COPY", "ADD") and any(Path(a).parts[:1] == (directory,) for a in args[:-1]):
            entered = True
        elif keyword == "WORKDIR" and args and directory in Path(args[0]).parts:
            entered = True
        elif keyword == "RUN" and entered:
            return True
    return False
from fastapi.testclient import TestClient

PAGE = Path("app/static/index.html")


def _capabilities():
    if not Path("app/actions").is_dir():
        return []
    return sorted(
        p.stem for p in Path("app/actions").glob("*.py") if p.stem != "__init__"
    )


def _html():
    if not PAGE.is_file():
        pytest.fail(
            "the platform serves no UI: app/static/index.html is missing"
        )
    return PAGE.read_text(encoding="utf-8", errors="replace")


def _ui_paths(html):
    return sorted(set(re.findall(r"/v1/[A-Za-z0-9_/\-]+", html)))


def _driven(html):
    """Capabilities the UI reaches: named outright, or discovered at runtime."""
    caps = _capabilities()
    paths = _ui_paths(html)
    discovers = "/v1/capabilities" in html and any(
        marker in html
        for marker in ('"/v1/" +', "'/v1/' +", "/v1/${", "`/v1/${")
    )
    if discovers:
        return caps
    return sorted(
        {c for c in caps if any(p.rstrip("/").endswith("/" + c) for p in paths)}
    )


def test_the_platform_serves_a_ui():
    assert _html().strip(), "app/static/index.html is empty"


def test_the_ui_reaches_more_than_one_capability():
    caps = _capabilities()
    if not caps:
        pytest.skip("this product ships no capabilities")
    driven = _driven(_html())
    need = min(2, len(caps))
    assert len(driven) >= need, (
        "the served UI drives %d of %d capability(ies) (%s): read "
        "/v1/capabilities and build the routes from it"
        % (len(driven), len(caps), ", ".join(driven) or "none")
    )


def test_every_route_the_ui_calls_answers():
    from app.main import app

    html = _html()
    declared = set()
    spec = Path("openapi.json")
    if spec.is_file():
        try:
            declared = set(
                (json.loads(spec.read_text(encoding="utf-8")).get("paths") or {}).keys()
            )
        except Exception:
            declared = set()

    token = os.environ.get("PLATFORM_TOKEN", "dev-local-token")
    auth = {"Authorization": "Bearer " + token}
    dead = []
    with TestClient(app) as client:
        for path in _ui_paths(html):
            if "{" in path or path.rstrip("/") == "/v1":
                continue
            if declared and path not in declared:
                continue  # an optional surface this product does not ship
            try:
                resp = client.get(path, headers=auth)
            except Exception as exc:
                dead.append("%s raised %s" % (path, type(exc).__name__))
                continue
            # 405 means the route exists and wants another verb.
            if resp.status_code in (404, 500, 501, 502):
                dead.append("%s answered %d" % (path, resp.status_code))
    assert not dead, "the UI calls routes the platform does not answer: %s" % dead


def test_the_formulas_are_reachable_from_the_ui():
    if not Path("app/formulas.py").is_file():
        pytest.skip("this product ships no formula layer")
    driven = _driven(_html())
    if not driven:
        pytest.skip("no capability is driven from the UI yet")
    for cap in driven:
        handler = Path("app/actions") / (cap + ".py")
        if handler.is_file() and _imports_formulas(handler):
            return
    pytest.fail(
        "app/formulas.py ships and no capability the UI drives uses it: "
        "the formula layer is not reachable from the product"
    )
