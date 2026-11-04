#!/usr/bin/env python3
"""Offline workbench agent: a bounded, deterministic edit-and-report runner.

The ``workbench`` block shells out to an agent CLI with a prompt file and a
bounded workspace (``--prompt @file --add-dir dir``). This platform runs
offline, so the CLI it invokes is this script: it reads the brief, inspects the
files in the bounded workspace, and writes a real report of what it found --
including a YAML parse and the schema keys of every track document present.

It never edits the operator's source tree (the workspace holds symlinks) and
never reaches the network.
"""

from __future__ import annotations

import argparse
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
    documents = []
    for path in sorted(workspace.rglob("*.yaml")) + sorted(workspace.rglob("*.yml")):
        if path.name == "kimi_prompt.md":
            continue
        entry = {"path": str(path.relative_to(workspace))}
        try:
            import yaml

            document = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001 - a broken file is a finding
            entry["error"] = f"{type(exc).__name__}: {exc}"
        else:
            if isinstance(document, dict):
                entry["keys"] = sorted(str(k) for k in document)
                entry["schema"] = document.get("schema")
                entry["weeks"] = document.get("weeks")
                entry["valid_yaml"] = True
            else:
                entry["valid_yaml"] = False
        documents.append(entry)
    return {
        "documents": documents,
        "document_count": len(documents),
        "all_valid": all(doc.get("valid_yaml") for doc in documents) if documents else False,
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
