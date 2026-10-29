"""The gate's contract with the product under test, read from what the product
itself prints and declares. Nothing here names a product.

* ``parse_score(text)`` -- the gate works the score out ITSELF from the per-row
  statuses the harness printed (``PASS``/``FAIL``/``SKIP`` lines, and the
  gate's own ``NOT_RUN``): k = PASS rows only (SKIP never counts), N = all rows.
  Rows are counted over the WHOLE output, and a FAIL row anywhere makes the
  result red. A summary line -- ``ACCEPTANCE: k/N`` or ``<LABEL> k/N
  ok=<bool>`` -- is only a claim. The LAST summary line is the one that must
  match the whole-output count (same k, same N, a declared verdict equal to
  k == N); where rows sit between summaries is informational only. A summary
  the rows do not back, including one with no rows at all, is REFUSED: no
  score, so the gate is red. ``<LABEL> k/N`` with no verdict (an informational
  ``EXTRA 3/4``) is not a summary. Rows with no summary: the derived score.
* ``token_env_names(harness)`` -- the environment variable names the product's
  own harness reads its bearer token from (``*_TOKEN`` read through
  ``os.environ[...]``, ``os.environ.get``, ``os.environ.setdefault`` or
  ``os.getenv``). The gate hands its per-run token to the container under each
  of these names, so the booted app and the harness agree on one token whatever
  the generated app calls it.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path
from typing import List, Optional, Tuple

_SCORE = re.compile(
    r"^(?:ACCEPTANCE:|(?P<label>[A-Z][A-Z0-9_]*))\s*(?P<k>\d+)\s*/\s*(?P<n>\d+)"
    r"(?:\s+ok=(?P<ok>True|False|true|false))?\s*$"
)
#: A per-row status line. Only PASS counts toward k; every row counts toward N.
_ROW = re.compile(r"^(?P<status>PASS|FAIL|SKIP|NOT_RUN)\b")

#: The gate's own name for its token, always passed as well.
GATE_TOKEN_ENV = "PLATFORM_TOKEN"


def parse_score(text: str) -> Optional[Tuple[int, int, bool]]:
    """Return (passed, total, ok) derived from per-row statuses, or None
    (refused / nothing measured)."""
    passed = total = failed = 0  # rows across the whole output
    last = None  # (claimed k, claimed N, declared ok) of the last summary
    for raw in (text or "").splitlines():
        line = raw.strip()
        row = _ROW.match(line)
        if row:
            total += 1
            passed += row.group("status") == "PASS"
            failed += row.group("status") == "FAIL"
            continue
        m = _SCORE.match(line)
        if not m or (m.group("label") is not None and m.group("ok") is None):
            continue  # not a summary (an informational k/N carries no verdict)
        last = (int(m.group("k")), int(m.group("n")), m.group("ok"))
    if total == 0:
        return None  # nothing measured; a summary alone is not backed
    ok = failed == 0 and passed == total
    if last is None:
        return passed, total, ok
    k, n, declared = last
    if (k, n) != (passed, total):
        return None  # the last summary is not the whole-output count: refused
    if declared is not None and (declared.lower() == "true") != ok:
        return None
    return passed, total, ok


def _env_name(node: ast.AST) -> Optional[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _is_environ(node: ast.AST) -> bool:
    return isinstance(node, ast.Attribute) and node.attr == "environ" and isinstance(node.value, ast.Name) and node.value.id == "os"


def token_env_names(harness: Path) -> List[str]:
    """``*_TOKEN`` names the harness reads from the environment, in order."""
    try:
        tree = ast.parse(Path(harness).read_text(encoding="utf-8"))
    except (OSError, SyntaxError, ValueError):
        return []
    found: List[str] = []
    for node in ast.walk(tree):
        name = None
        if isinstance(node, ast.Subscript) and _is_environ(node.value):
            name = _env_name(node.slice)
        elif isinstance(node, ast.Call) and node.args:
            f = node.func
            if isinstance(f, ast.Attribute) and f.attr in {"get", "setdefault"} and _is_environ(f.value):
                name = _env_name(node.args[0])
            elif isinstance(f, ast.Attribute) and f.attr == "getenv" and isinstance(f.value, ast.Name) and f.value.id == "os":
                name = _env_name(node.args[0])
        if name and name.endswith("_TOKEN") and re.fullmatch(r"[A-Z][A-Z0-9_]*", name) and name not in found:
            found.append(name)
    return found


def token_envs(harness: Path) -> List[str]:
    """The names the gate passes its token under: the gate's own, then the harness's."""
    names = [GATE_TOKEN_ENV]
    for n in token_env_names(harness):
        if n not in names:
            names.append(n)
    return names


def main(argv: List[str]) -> int:
    if len(argv) == 3 and argv[1] == "token-envs":
        print(" ".join(token_envs(Path(argv[2]))))
        return 0
    print("usage: gate_contract.py token-envs <harness.py>", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
