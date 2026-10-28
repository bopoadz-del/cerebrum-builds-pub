"""B-2: the gate reads the score the harness actually prints, and hands its
token to the app under the name the product's harness uses. Each fix is
driven with two different inputs, through the helper and through the real
workflow steps."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import gate_contract  # noqa: E402

WORKFLOW = HERE.parent / "workflows" / "store-gate.yml"
PARSE = "Parse k/N and write result"
TOKENS = "Read the token names the product's harness uses"
BASH = shutil.which("bash") or "bash"


def _step(name):
    steps = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]["store-gate"]["steps"]
    return next(s for s in steps if s.get("name") == name)


def _tree(tmp_path):
    run = tmp_path / "run"
    (run / ".github" / "store_gate").mkdir(parents=True)
    shutil.copy(HERE / "gate_contract.py", run / ".github" / "store_gate" / "gate_contract.py")
    (run / "scripts").mkdir()
    return run


def _run(run, name, env_extra=None):
    github_env = run.parent / "github_env"
    github_env.write_text("", encoding="utf-8")
    script = run.parent / "step.sh"
    script.write_text(_step(name)["run"], encoding="utf-8", newline="\n")
    shims = run.parent / "bin"
    shims.mkdir(exist_ok=True)
    py = shims / "python3"
    py.write_text(f'#!/usr/bin/env bash\nexec "{Path(sys.executable).as_posix()}" "$@"\n', encoding="utf-8")
    py.chmod(0o755)
    env = dict(os.environ)
    for k in ("IMAGE_BUILT", "BOOT_CRASHED", "REPLAY_LABEL", "BUILD_SHA"):
        env.pop(k, None)
    env["PATH"] = f"{shims}{os.pathsep}{env.get('PATH', '')}"
    env["GITHUB_ENV"] = str(github_env)
    env["GITHUB_SHA"] = "f" * 40
    env.update(env_extra or {})
    proc = subprocess.run([BASH, "-e", str(script)], cwd=run, env=env, capture_output=True, text=True, timeout=60)
    recorded = dict(l.split("=", 1) for l in github_env.read_text(encoding="utf-8").splitlines() if "=" in l)
    return proc, recorded


# -- fix 1: the score the gate actually prints -------------------------------------------------


@pytest.mark.parametrize(
    "printed, want",
    [
        ("PASS a — ok\nACCEPTANCE: 22/22\n", (22, 22, True)),
        ("PASS a — ok\nFAIL b — no\nSTORE 12/13 ok=False\nEXTRA 4/4\n", (12, 13, False)),
        ("STORE 13/13 ok=True\nEXTRA 1/4\n", (13, 13, True)),
        ("ACCEPTANCE: 3/5\n", (3, 5, False)),
    ],
)
def test_parse_score_reads_either_printed_format(printed, want):
    assert gate_contract.parse_score(printed) == want


def test_a_line_without_its_own_verdict_is_not_the_score():
    assert gate_contract.parse_score("EXTRA 4/4\n") is None
    assert gate_contract.parse_score("STORE 13/13 ok=False\n") == (13, 13, False)
    assert gate_contract.parse_score("") is None


@pytest.mark.parametrize(
    "printed, score, ok",
    [("ACCEPTANCE: 21/22\n", "21/22", False), ("STORE 13/13 ok=True\nEXTRA 2/5\n", "13/13", True)],
)
def test_the_workflow_parse_step_scores_what_the_harness_printed(tmp_path, printed, score, ok):
    run = _tree(tmp_path)
    (run / "acceptance.out").write_text(printed, encoding="utf-8")
    proc, _ = _run(run, PARSE)
    report = json.loads((run / "store_gate.json").read_text(encoding="utf-8"))
    assert report["score"] == score and report["ok"] is ok, (proc.stdout, proc.stderr)
    assert proc.returncode == (0 if ok else 1)


# -- fix 2: the token name matches the generated app's ----------------------------------------


@pytest.mark.parametrize(
    "harness, want",
    [
        ('import os\nos.environ.setdefault("OPERATOR_TOKEN", "x")\nH = os.environ["OPERATOR_TOKEN"]\n', ["OPERATOR_TOKEN"]),
        ('import os\nT = os.getenv("SERVICE_API_TOKEN")\nU = os.environ.get("DATABASE_URL")\n', ["SERVICE_API_TOKEN"]),
    ],
)
def test_token_env_names_come_from_the_harness(tmp_path, harness, want):
    path = tmp_path / "acceptance.py"
    path.write_text(harness, encoding="utf-8")
    assert gate_contract.token_env_names(path) == want
    assert gate_contract.token_envs(path) == ["PLATFORM_TOKEN", *want]


def test_an_unreadable_harness_keeps_the_gate_s_own_name(tmp_path):
    assert gate_contract.token_envs(tmp_path / "missing.py") == ["PLATFORM_TOKEN"]


@pytest.mark.parametrize("name", ["OPERATOR_TOKEN", "SERVICE_API_TOKEN"])
def test_the_workflow_records_the_harness_s_token_name(tmp_path, name):
    run = _tree(tmp_path)
    (run / "scripts" / "acceptance.py").write_text(f'import os\nos.environ.setdefault("{name}", "x")\n', encoding="utf-8")
    proc, recorded = _run(run, TOKENS)
    assert proc.returncode == 0, proc.stderr
    assert recorded["APP_TOKEN_ENVS"].split() == ["PLATFORM_TOKEN", name]


def test_every_container_gets_the_token_under_the_recorded_names():
    wf = WORKFLOW.read_text(encoding="utf-8")
    assert 'PLATFORM_TOKEN="$GATE_PLATFORM_TOKEN"' not in wf  # no fixed name left
    for step in ("Run scripts/acceptance.py inside the image",):
        run = _step(step)["run"]
        assert 'for name in ${APP_TOKEN_ENVS:-PLATFORM_TOKEN}' in run and "$TOKEN_ARGS" in run
    assert wf.count("$TOKEN_ARGS \\") == 3  # postgres probe, gate container, harness exec


# -- B-2 rework 1: mixed formats, multi-line, the LAST score line wins -------------------------


@pytest.mark.parametrize(
    "printed, want",
    [
        ("ACCEPTANCE: 1/2\nSTORE 2/2 ok=True\n", (2, 2, True)),
        ("STORE 2/2 ok=True\nACCEPTANCE: 1/2\n", (1, 2, False)),
        ("ACCEPTANCE: 0/4\nPASS x\nACCEPTANCE: 4/4\nEXTRA 0/9\n", (4, 4, True)),
        ("STORE 3/3 ok=True\nFAIL y\nSTORE 2/3 ok=False\n", (2, 3, False)),
    ],
)
def test_the_last_score_line_wins_across_formats(printed, want):
    assert gate_contract.parse_score(printed) == want
