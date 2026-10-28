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


R3 = "PASS a - ok\nPASS b - ok\nPASS c - ok\n"


@pytest.mark.parametrize(
    "printed, want",
    [
        (R3 + "ACCEPTANCE: 3/3\n", (3, 3, True)),
        ("PASS a - ok\nFAIL b - no\nACCEPTANCE: 1/2\n", (1, 2, False)),
        (R3 + "STORE 3/3 ok=True\nEXTRA 1/4\n", (3, 3, True)),
        ("PASS a - ok\nFAIL b - no\nSTORE 1/2 ok=False\nEXTRA 4/4\n", (1, 2, False)),
    ],
)
def test_parse_score_reads_either_printed_format(printed, want):
    assert gate_contract.parse_score(printed) == want


def test_a_line_without_its_own_verdict_is_not_the_score():
    assert gate_contract.parse_score("EXTRA 4/4\n") is None
    assert gate_contract.parse_score("PASS a\nFAIL b\nEXTRA 2/2\n") == (1, 2, False)  # rows, derived
    assert gate_contract.parse_score("") is None


@pytest.mark.parametrize(
    "printed, score, ok",
    [
        ("PASS a\nFAIL b\nACCEPTANCE: 1/2\n", "1/2", False),
        (R3 + "STORE 3/3 ok=True\nEXTRA 2/5\n", "3/3", True),
    ],
)
def test_the_workflow_parse_step_scores_what_the_harness_printed(tmp_path, printed, score, ok):
    run = _tree(tmp_path)
    (run / "acceptance.out").write_text(printed, encoding="utf-8")
    proc, _ = _run(run, PARSE)
    report = json.loads((run / "store_gate.json").read_text(encoding="utf-8"))
    assert report["score"] == score and report["ok"] is ok, (proc.stdout, proc.stderr)
    assert proc.returncode == (0 if ok else 1)


# -- 0900Z: the gate derives k/N from rows; SKIP never counts; unbacked summaries are refused --


@pytest.mark.parametrize(
    "printed",
    [
        "PASS boot\nSKIP x\nSKIP y\nSTORE 3/3 ok=True\n",
        "PASS health\nSKIP a\nPASS b\nSKIP c\nGATE 4/4 ok=True\nEXTRA 1/1\n",
    ],
)
def test_a_skip_inflated_summary_is_not_green(printed):
    got = gate_contract.parse_score(printed)
    assert got is None or got[2] is False


@pytest.mark.parametrize(
    "printed, want",
    [
        ("PASS boot\nSKIP x\nSKIP y\n", (1, 3, False)),
        ("PASS health\nSKIP a\nPASS b\nSKIP c\n", (2, 4, False)),
    ],
)
def test_skip_rows_count_in_n_never_in_k(printed, want):
    assert gate_contract.parse_score(printed) == want


@pytest.mark.parametrize(
    "printed, want",
    [
        ("PASS boot\nPASS x\nPASS y\nSTORE 3/3 ok=True\n", (3, 3, True)),
        ("PASS health\nPASS a\nPASS b\nPASS c\nGATE 4/4 ok=True\nEXTRA 1/1\n", (4, 4, True)),
    ],
)
def test_an_honest_all_pass_summary_is_green(printed, want):
    assert gate_contract.parse_score(printed) == want


@pytest.mark.parametrize(
    "printed",
    [
        "STORE 3/3 ok=True\n",
        "ACCEPTANCE: 22/22\n",
        "STORE 13/13 ok=True\nEXTRA 1/4\n",
        "ACCEPTANCE: 3/5\n",
    ],
)
def test_a_summary_only_input_gets_no_score(printed):
    assert gate_contract.parse_score(printed) is None


@pytest.mark.parametrize(
    "printed",
    [
        "PASS a\nACCEPTANCE: 22/22\n",  # N not backed
        "PASS a\nFAIL b\nSTORE 2/2 ok=True\n",  # k not backed
        "PASS a\nPASS b\nSTORE 2/2 ok=False\n",  # verdict not backed
        "PASS a\nACCEPTANCE: 1/1\nFAIL late\n",  # a row after the last summary
    ],
)
def test_a_summary_the_rows_do_not_back_is_refused(printed):
    assert gate_contract.parse_score(printed) is None


@pytest.mark.parametrize(
    "printed",
    ["PASS boot\nSKIP x\nSKIP y\nSTORE 3/3 ok=True\n", "ACCEPTANCE: 22/22\n"],
)
def test_the_workflow_parse_step_refuses_an_unbacked_summary(tmp_path, printed):
    run = _tree(tmp_path)
    (run / "acceptance.out").write_text(printed, encoding="utf-8")
    proc, _ = _run(run, PARSE)
    report = json.loads((run / "store_gate.json").read_text(encoding="utf-8"))
    assert report["score"] == "no score" and report["ok"] is False
    assert proc.returncode != 0


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
        ("PASS a\nFAIL b\nACCEPTANCE: 1/2\nPASS a\nPASS b\nSTORE 2/2 ok=True\n", (2, 2, True)),
        ("PASS a\nPASS b\nSTORE 2/2 ok=True\nPASS a\nFAIL b\nACCEPTANCE: 1/2\n", (1, 2, False)),
        ("FAIL a\nFAIL b\nACCEPTANCE: 0/2\nPASS a\nPASS b\nACCEPTANCE: 2/2\nEXTRA 0/9\n", (2, 2, True)),
        ("PASS a\nPASS b\nSTORE 2/2 ok=True\nPASS a\nFAIL b\nSTORE 1/2 ok=False\n", (1, 2, False)),
    ],
)
def test_the_last_score_line_wins_across_formats(printed, want):
    assert gate_contract.parse_score(printed) == want
