"""Branch hygiene against a real git remote (a local bare repo)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import branch_hygiene as bh  # noqa: E402


def _git(args, cwd, env=None):
    proc = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True,
                          env={**os.environ, **(env or {})})
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


@pytest.fixture()
def remote(tmp_path):
    bare = tmp_path / "builds.git"
    _git(["init", "-q", "--bare", str(bare)], tmp_path)
    return str(bare)


def _branch(remote, tmp_path, branch, files, when):
    work = tmp_path / ("w-" + branch.replace("/", "_"))
    work.mkdir()
    _git(["init", "-q"], work)
    for rel, text in files.items():
        p = work / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(text.encode("utf-8"))
    _git(["add", "-A"], work)
    stamp = f"{when.isoformat()}T12:00:00+00:00"
    _git(["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "c"], work,
         env={"GIT_AUTHOR_DATE": stamp, "GIT_COMMITTER_DATE": stamp})
    _git(["push", "-q", remote, f"HEAD:refs/heads/{branch}"], work)
    return _git(["rev-parse", "HEAD"], work)


def test_an_idle_branch_is_tagged_then_deleted_and_the_tree_survives(remote, tmp_path):
    old = "build/plt_0123456789abcdef"
    fresh = "build/plt_fedcba9876543210"
    sha = _branch(remote, tmp_path, old, {"app/main.py": "x = 1\n"}, date(2026, 1, 1))
    _branch(remote, tmp_path, fresh, {"app/main.py": "y = 2\n"}, date(2026, 9, 30))

    lines = bh.run(remote, today=date(2026, 10, 5), days=90)

    assert [line["action"] for line in lines] == ["archived"]
    assert lines[0]["tag"] == "archive/plt_0123456789abcdef/2026-10-05"
    assert bh.tag_sha(remote, lines[0]["tag"]) == sha  # the tag keeps the tree
    branches = bh.build_branches(remote)
    assert old not in branches and fresh in branches  # active platform untouched
    restored = tmp_path / "restored"
    _git(["init", "-q", str(restored)], tmp_path)
    _git(["fetch", "-q", remote, "refs/tags/" + lines[0]["tag"]], restored)
    assert _git(["show", "FETCH_HEAD:app/main.py"], restored) == "x = 1"


def test_a_head_is_never_deleted_when_its_tag_does_not_hold_it(remote, tmp_path, monkeypatch):
    branch = "build/plt_0123456789abcdef"
    _branch(remote, tmp_path, branch, {"a": "1\n"}, date(2026, 1, 1))
    monkeypatch.setattr(bh, "tag_sha", lambda r, tag: "0" * 40)
    lines = bh.run(remote, today=date(2026, 10, 5), days=90)
    assert lines[0]["action"] == "error"
    assert branch in bh.build_branches(remote)


def test_dry_run_moves_nothing(remote, tmp_path):
    branch = "build/plt_0123456789abcdef"
    _branch(remote, tmp_path, branch, {"a": "1\n"}, date(2026, 1, 1))
    lines = bh.run(remote, today=date(2026, 10, 5), days=90, dry_run=True)
    assert lines[0]["action"] == "would_archive"
    assert branch in bh.build_branches(remote)


def test_every_action_and_the_run_summary_reach_the_ledger(remote, tmp_path):
    _branch(remote, tmp_path, "build/plt_0123456789abcdef", {"a": "1\n"}, date(2026, 1, 1))
    out = tmp_path / "ledger.jsonl"
    code = bh.main(["--remote", remote, "--ledger-out", str(out), "--today", "2026-10-05",
                    "--repo-size-kb", "1234"])
    rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert code == 0
    assert rows[0]["action"] == "archived"
    assert rows[-1] == {
        "action": "run", "archived": 1, "at": "2026-10-05", "errors": 0,
        "live_build_branches": 0, "repo_size_kb": 1234,
    }
