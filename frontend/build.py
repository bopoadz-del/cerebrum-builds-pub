#!/usr/bin/env python3
"""Render the console the product serves at "/" -- without node.

The Dockerfile runs ``python3 frontend/build.py`` during the image build, so
this script is stdlib-only and network-free by construction: no npm, no
bundler, no package download. It validates the console asset
(``frontend/dist/index.html``, a single self-contained page kept in step with
the React/TypeScript sources under ``src/``) and renders it to
``app/static/index.html``, the file ``app/main.py`` serves at ``/``.

The validation is the build gate for the page: it must discover the roster
from ``/v1/capabilities``, build capability paths from what it discovers, keep
the operator's token in browser storage, carry no bundled credential, and
fetch nothing off-box.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "frontend" / "dist" / "index.html"
OUTPUT = ROOT / "app" / "static" / "index.html"

REQUIRED_MARKERS = ('"/v1/capabilities"', '"/v1/" +', 'id="token"')
STORAGE_MARKERS = ("sessionStorage", "localStorage")
CREDENTIAL_PATTERNS = (
    (re.compile(r"""["']Bearer\s+[A-Za-z0-9._\-]{8,}["']"""), "a literal bearer credential"),
    (re.compile(r"""\btoken\s*[:=]\s*["'][A-Za-z0-9._\-]{12,}["']"""), "a literal token assignment"),
)
OFFBOX = re.compile(r"""(?:https?:)?//[A-Za-z0-9]""")


def read_source() -> str:
    for candidate in (SOURCE, OUTPUT):
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8")
    raise SystemExit("no console source found: expected %s" % SOURCE)


def validate(page: str) -> list:
    problems = []
    for marker in REQUIRED_MARKERS:
        if marker not in page:
            problems.append("missing required marker: %s" % marker)
    if not any(marker in page for marker in STORAGE_MARKERS):
        problems.append("page keeps the operator token in no browser storage")
    if '"Bearer "' not in page:
        problems.append('page never builds a bearer header (expected "Bearer " plus a variable)')
    for pattern, description in CREDENTIAL_PATTERNS:
        found = pattern.search(page)
        if found:
            problems.append("page carries %s: %r" % (description, found.group(0)))
    for found in OFFBOX.finditer(page):
        problems.append("page references an off-box URL: %r" % found.group(0))
    return problems


def render(check_only: bool = False) -> int:
    page = read_source()
    problems = validate(page)
    if problems:
        for problem in problems:
            print("console build refused: %s" % problem, file=sys.stderr)
        return 1
    data = page.encode("utf-8")
    if check_only:
        print("console source validated: %d bytes" % len(data))
        return 0
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    if OUTPUT.is_file() and OUTPUT.read_bytes() == data:
        print("console up to date: %s (%d bytes)" % (OUTPUT, len(data)))
        return 0
    OUTPUT.write_bytes(data)
    print("console rendered: %s (%d bytes)" % (OUTPUT, len(data)))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Render the served console from frontend/.")
    parser.add_argument("--check", action="store_true", help="validate without writing")
    args = parser.parse_args(argv)
    return render(check_only=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
