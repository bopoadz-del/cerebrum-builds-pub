#!/usr/bin/env python3
"""Offline workbench agent: a bounded, deterministic inspect-and-report runner.

The ``workbench`` block shells out to an agent CLI with a prompt file and a
bounded workspace (``--prompt @file --add-dir dir``). This platform runs
offline, so the CLI it invokes is this script: it reads the brief, inspects the
records placed in the bounded workspace, and writes a real report of what it
found. It never edits the operator's source tree, never creates files outside
the bounded workspace, and never reaches the network.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


def _read_prompt(value: str) -> str:
    if value.startswith("@"):
        path = Path(value[1:])
        if path.is_file():
            return path.read_text(encoding="utf-8", errors="replace")
    return value


def _inspect(workspace: Path) -> dict:
    records = []
    for path in sorted(workspace.rglob("*")):
        if not path.is_file() or path.name in ("kimi_prompt.md", "workbench_report.json"):
            continue
        entry = {
            "path": str(path.relative_to(workspace)),
            "size": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        if path.suffix.lower() in (".json", ".jsonl"):
            try:
                entry["json"] = json.loads(path.read_text(encoding="utf-8"))
                entry["valid_json"] = True
            except Exception as exc:  # noqa: BLE001 - a broken file is a finding
                entry["valid_json"] = False
                entry["error"] = f"{type(exc).__name__}: {exc}"
        elif path.suffix.lower() in (".csv", ".txt", ".md"):
            text = path.read_text(encoding="utf-8", errors="replace")
            entry["lines"] = len(text.splitlines())
            entry["preview"] = text[:500]
        records.append(entry)
    return {
        "records": records,
        "record_count": len(records),
        "all_readable": all("error" not in row for row in records) if records else False,
    }


def main(argv: list) -> int:
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--add-dir", action="append", default=[])
    args = parser.parse_args(argv)

    brief = _read_prompt(args.prompt)
    workspace = Path(args.add_dir[0]).resolve() if args.add_dir else Path.cwd()
    report = {
        "agent": "offline-workbench",
        "brief": brief[:4000],
        "workspace": str(workspace),
        "inspection": _inspect(workspace),
    }
    target = workspace / "workbench_report.json"
    target.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"ok": True, "report": str(target)}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
