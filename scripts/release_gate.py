#!/usr/bin/env python3
"""Release gate for car manufacturing platform.

Runs the platform's own *code-phase* suite (pytest -m "not pilot") and
prints a PASS/FAIL verdict. Store-backed execute-all lives on
@pytest.mark.pilot and is a later phase, not this gate.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


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


def main() -> int:
    print("== car manufacturing platform — release gate ==")
    try:
        import pytest  # noqa: F401
    except ImportError:
        print("pytest is not installed, so the suite cannot be run.")
        print("  pip install -r requirements-dev.txt")
        print("VERDICT: CANNOT RUN")
        return 2
    # Literal sys.executable. Extra braces make {sys.executable} a set,
    # which compiles then TypeError's in Popen (py_compile cannot catch it).
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests", "-q", "-m", "not pilot"],
        cwd=ROOT,
    )
    ok = result.returncode == 0

    lock = ROOT / "blocks.lock.json"
    if lock.is_file():
        data = json.loads(lock.read_text(encoding="utf-8"))
        blocks = data.get("blocks", {})
        print(f"vendored blocks: {len(blocks)}")
        for bid, meta in sorted(blocks.items()):
            print(f"  {bid} @ {str(meta.get('commit'))[:16]} ({meta.get('source')})")
        runtime = data.get("runtime")
        if runtime:
            print(f"store runtime slice: {len(runtime.get('files', []))} file(s) "
                  f"@ {str(runtime.get('commit'))[:16]}")
    else:
        print("blocks.lock.json: MISSING — provenance of vendored blocks is unknown")
        ok = False

    manifest = ROOT / "docs" / "build_provenance.json"
    if manifest.is_file():
        prov = json.loads(manifest.read_text(encoding="utf-8"))
        sources = prov.get("artifact_sources", {})
        agent = sorted(
            k
            for k, v in sources.items()
            # The Factory's one authorship vocabulary (authorship.py).
            if str(v).startswith(('coder LLM', 'coder CLI', 'FACTORY_CODE_CLI', 'codewhale'))
        )
        print(f"artifacts: {len(sources)} total, {len(agent)} written by the coding agent")
    else:
        # docs/build_provenance.json is the factory's own record and does not
        # ship (builds_push.FACTORY_INTERNAL_PATHS), so a delivered platform
        # never has it. Demanding it here failed the image build of every
        # platform at Dockerfile's release-gate step -- a suite with 108
        # passing tests was reported as 0/13 because acceptance never ran.
        # Report authorship from what IS in the tree: the stamp each handler
        # carries in its own source. Reported, not judged -- the acceptance
        # floor's authorship_floor check is the one place that is decided.
        actions = ROOT / "app" / "actions"
        handlers = [
            p for p in sorted(actions.glob("*.py")) if not p.name.startswith("_")
        ] if actions.is_dir() else []
        # The SAME rule the acceptance floor's authorship_floor uses: each
        # handler's module-level AUTHORED_BY assignment, read from the
        # syntax tree by a reader rendered from the Factory's canonical one,
        # so the delivered tree needs no app/factory import. A docstring
        # sentence decides nothing.
        _agent_prefixes = ('coder LLM', 'coder CLI', 'FACTORY_CODE_CLI', 'codewhale')
        _agent_exact = {'harvested workspace handler', 'compiled-brief oneshot'}
        stamped = 0
        for path in handlers:
            _src = _authored_by(path.read_text(encoding="utf-8", errors="replace"))
            if _src and (_src.startswith(_agent_prefixes) or _src.lower() in _agent_exact):
                stamped += 1
        print(f"handlers: {len(handlers)} total, {stamped} stamped by the coding agent")

    print("VERDICT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
