"""The gate's contract with the product under test, read from what the product
itself prints and declares. Nothing here names a product.

* ``parse_score(text)`` -- the score the harness actually printed. A score line
  is either ``ACCEPTANCE: k/N`` or a summary line that carries its own verdict,
  ``<LABEL> k/N ok=<True|False>`` (for example a harness that prints its floor as
  ``STORE 13/13 ok=True``). A ``k/N`` line without a verdict (an informational
  ``EXTRA 3/4``) is not a score. The LAST score line wins. Green only when
  N > 0, k == N, and any declared verdict agrees.
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
    r"(?:\s+ok=(?P<ok>True|False|true|false))?\s*$",
    re.MULTILINE,
)

#: The gate's own name for its token, always passed as well.
GATE_TOKEN_ENV = "PLATFORM_TOKEN"


def parse_score(text: str) -> Optional[Tuple[int, int, bool]]:
    """Return (passed, total, ok) from the last score line, or None."""
    last = None
    for m in _SCORE.finditer(text or ""):
        if m.group("label") is not None and m.group("ok") is None:
            continue  # a k/N line with no verdict of its own is not the score
        last = m
    if last is None:
        return None
    passed, total = int(last.group("k")), int(last.group("n"))
    ok = total > 0 and passed == total
    declared = last.group("ok")
    if declared is not None:
        ok = ok and declared.lower() == "true"
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
