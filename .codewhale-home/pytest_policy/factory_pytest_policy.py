"""Factory pytest policy -- Factory-owned, re-stamped on every writer pass.

A pytest run that is not the targeted set for the files this pass changed
is refused: the code-phase gate and TESTER own the suites, and the Factory
runs them itself. Run the targeted set (``python scripts/factory_checks.py`` runs it).
"""

import json
import os
import time
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parent
SELF_CHECK_REL = 'scripts/factory_checks.py'
SELF_CHECK_COPY = 'factory_self_check_source.py'
DENIALS_FILE = 'denials.jsonl'
ROOT_ENV = 'FACTORY_PYTEST_POLICY_ROOT'


def _norm_test_path(arg):
    import posixpath
    path = arg.split('::', 1)[0].replace('\\', '/')
    return posixpath.normpath(path)


def is_suite_run(selection, targeted):
    """True when a pytest invocation is NOT confined to the targeted set.

    No path selects the whole collection; a path that is not a test FILE (a
    directory) selects everything under it; a file outside ``targeted`` (the
    self-check's selection at that moment) is not targeted. ``targeted`` None
    means the set could not be computed: only the shape is judged.
    """
    if not selection:
        return True
    allowed = None if targeted is None else {_norm_test_path(t) for t in targeted}
    for arg in selection:
        path = _norm_test_path(arg)
        if not path.endswith('.py'):
            return True
        if allowed is not None and path not in allowed:
            return True
    return False


def _targeted(root):
    """The self-check's targeted set now; None when it cannot be computed."""
    try:
        namespace = {
            "__name__": "factory_policy_targeted",
            "__file__": os.path.join(root, SELF_CHECK_REL),
        }
        source = (_HERE / SELF_CHECK_COPY).read_text(encoding="utf-8")
        exec(compile(source, SELF_CHECK_REL, "exec"), namespace)
        changed = namespace["_changed_sources"](root)
        return list(
            namespace["select_targeted_tests"](
                changed, namespace["_test_files"](root)
            )
        )
    except Exception:
        return None


def _selection(config, root):
    """The paths this invocation selects, root-relative; [] = no explicit path."""
    source = getattr(config, "args_source", None)
    if source is not None and source != pytest.Config.ArgsSource.ARGS:
        return []
    base = str(config.invocation_params.dir)
    out = []
    for arg in config.args:
        path, sep, rest = str(arg).partition("::")
        full = os.path.normpath(os.path.join(base, path))
        rel = os.path.relpath(full, root).replace(os.sep, "/")
        out.append(rel + sep + rest)
    return out


def _record(entry):
    try:
        with open(_HERE / DENIALS_FILE, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, sort_keys=True) + "\n")
    except OSError:
        pass


@pytest.hookimpl(tryfirst=True)
def pytest_cmdline_main(config):
    root = os.environ.get(ROOT_ENV)
    if not root:
        return None
    if config.getoption("version", False) or config.getoption("help", False):
        return None
    selection = _selection(config, root)
    targeted = _targeted(root)
    if not is_suite_run(selection, targeted):
        return None
    _record(
        {
            "t": time.time(),
            "selection": selection,
            "targeted": targeted,
        }
    )
    named = ", ".join(targeted or []) or "none (no changed source has a test yet)"
    raise pytest.UsageError(
        "factory policy: this pytest run is not the targeted set and is "
        "refused (the code-phase gate and TESTER run the suites). "
        f"Targeted set now: {named}"
    )
