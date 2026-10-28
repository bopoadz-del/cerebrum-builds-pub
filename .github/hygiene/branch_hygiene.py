"""Nightly branch hygiene for cerebrum-builds.

One platform = one branch (``build/<platform_id>``), forever -- but a platform
nobody has touched for 90 days does not need a live branch. Its head is
tagged ``archive/<id>/<YYYY-MM-DD>``, the tag is read back at that exact sha,
and only then is the branch deleted: the tag keeps the full tree, and the
Factory's "Continue" recreates the branch from it.

A head is never deleted without a tag holding it. Every action is one JSON
line on the hygiene ledger; the run's last line reports the repo size.

Usage: python branch_hygiene.py --remote origin --ledger-out lines.jsonl
       [--days 90] [--today YYYY-MM-DD] [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

BRANCH_REF_PREFIX = "refs/heads/build/"
TAG_REF_PREFIX = "refs/tags/"
ARCHIVE_PREFIX = "archive/"
STALE_DAYS = 90


class HygieneError(RuntimeError):
    pass


def _git(args, cwd: Optional[Path] = None) -> subprocess.CompletedProcess:
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    return subprocess.run(["git", *args], cwd=str(cwd or Path.cwd()), capture_output=True,
                          text=True, env=env, timeout=600)


def _ls_remote(remote: str, pattern: str) -> List[Tuple[str, str]]:
    proc = _git(["ls-remote", remote, pattern])
    if proc.returncode != 0:
        raise HygieneError(f"ls-remote failed: {proc.stderr[-300:]}")
    rows = []
    for line in proc.stdout.splitlines():
        parts = line.split()
        if len(parts) == 2:
            rows.append((parts[0], parts[1]))
    return rows


def build_branches(remote: str) -> Dict[str, str]:
    """``{branch: sha}`` for every ``build/**`` branch."""
    return {name[len("refs/heads/"):]: sha for sha, name in _ls_remote(remote, BRANCH_REF_PREFIX + "*")}


def tag_sha(remote: str, tag: str) -> Optional[str]:
    rows = {name: sha for sha, name in _ls_remote(remote, TAG_REF_PREFIX + tag + "*")}
    return rows.get(TAG_REF_PREFIX + tag + "^{}") or rows.get(TAG_REF_PREFIX + tag)


def head_time(remote: str, sha: str, work: Path) -> datetime:
    """Committer time of ``sha`` (the branch's last activity)."""
    fetched = _git(["fetch", "-q", "--depth=1", remote, sha], work)
    if fetched.returncode != 0:
        raise HygieneError(f"fetch {sha[:12]} failed: {fetched.stderr[-300:]}")
    shown = _git(["log", "-1", "--format=%ct", sha], work)
    return datetime.fromtimestamp(int(shown.stdout.strip()), tz=timezone.utc)


def platform_part(branch: str) -> str:
    """``build/<id>`` -> ``<id>``: the archive tag's middle segment."""
    return branch[len("build/"):]


def archive_tag_for(remote: str, branch: str, day: date, sha: str) -> str:
    """``archive/<id>/<day>``; a second archive the same day gets ``.2`` ..."""
    base = f"{ARCHIVE_PREFIX}{platform_part(branch)}/{day.isoformat()}"
    candidate, n = base, 1
    while True:
        existing = tag_sha(remote, candidate)
        if existing is None or existing == sha:
            return candidate
        n += 1
        candidate = f"{base}.{n}"


def archive(remote: str, branch: str, sha: str, day: date, work: Path) -> dict:
    """Tag, read the tag back at ``sha``, THEN delete the branch."""
    tag = archive_tag_for(remote, branch, day, sha)
    if tag_sha(remote, tag) is None:
        pushed = _git(["push", "-q", remote, f"{sha}:{TAG_REF_PREFIX}{tag}"], work)
        if pushed.returncode != 0:
            raise HygieneError(f"tag {tag} failed: {pushed.stderr[-300:]}")
    if tag_sha(remote, tag) != sha:
        raise HygieneError(f"refusing to delete {branch}: tag {tag} does not hold {sha[:12]}")
    deleted = _git(["push", "-q", remote, f"--force-with-lease=refs/heads/{branch}:{sha}",
                    f":refs/heads/{branch}"], work)
    if deleted.returncode != 0:
        raise HygieneError(f"delete {branch} failed: {deleted.stderr[-300:]}")
    return {"action": "archived", "branch": branch, "tag": tag, "sha": sha}


def run(remote: str, *, today: date, days: int = STALE_DAYS, dry_run: bool = False) -> List[dict]:
    """Archive every build branch idle for ``days``; one ledger line per action."""
    lines: List[dict] = []
    cutoff = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc) - timedelta(days=days)
    with tempfile.TemporaryDirectory(prefix="hygiene-") as tmp:
        work = Path(tmp)
        _git(["init", "-q"], work)
        for branch, sha in sorted(build_branches(remote).items()):
            when = head_time(remote, sha, work)
            if when >= cutoff:
                continue
            base = {"at": today.isoformat(), "last_activity": when.date().isoformat()}
            if dry_run:
                lines.append({**base, "action": "would_archive", "branch": branch, "sha": sha})
                continue
            try:
                lines.append({**base, **archive(remote, branch, sha, today, work)})
            except HygieneError as exc:
                lines.append({**base, "action": "error", "branch": branch, "sha": sha, "error": str(exc)})
    return lines


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--ledger-out", required=True)
    parser.add_argument("--days", type=int, default=STALE_DAYS)
    parser.add_argument("--today", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--repo-size-kb", type=int, default=None)
    args = parser.parse_args(argv)
    today = date.fromisoformat(args.today) if args.today else datetime.now(timezone.utc).date()
    lines = run(args.remote, today=today, days=args.days, dry_run=args.dry_run)
    summary = {
        "at": today.isoformat(),
        "action": "run",
        "archived": sum(1 for line in lines if line["action"] == "archived"),
        "errors": sum(1 for line in lines if line["action"] == "error"),
        "repo_size_kb": args.repo_size_kb,
        "live_build_branches": len(build_branches(args.remote)),
    }
    with open(args.ledger_out, "a", encoding="utf-8") as fh:
        for line in [*lines, summary]:
            fh.write(json.dumps(line, sort_keys=True) + "\n")
    print(json.dumps(summary))
    return 1 if summary["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
