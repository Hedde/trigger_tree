"""Shared helpers: load the hyphen-named scripts as modules with a controlled
CLAUDE_PROJECT_DIR. Each load executes the module fresh, so per-test project
roots work and coverage accumulates across loads."""

import importlib.util
import os
import sys
import uuid

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(REPO, "scripts")
FIXTURE = os.path.join(REPO, "tests", "fixture-project")

__all__ = ["REPO", "SCRIPTS", "FIXTURE", "load_script"]


def load_script(filename, project_root):
    old = os.environ.get("CLAUDE_PROJECT_DIR")
    os.environ["CLAUDE_PROJECT_DIR"] = str(project_root)
    sys.path.insert(0, SCRIPTS)
    try:
        name = filename.replace("-", "_").replace(".py", "") + "_" + uuid.uuid4().hex[:8]
        spec = importlib.util.spec_from_file_location(name, os.path.join(SCRIPTS, filename))
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
        return mod
    finally:
        sys.path.remove(SCRIPTS)
        if old is None:
            os.environ.pop("CLAUDE_PROJECT_DIR", None)
        else:
            os.environ["CLAUDE_PROJECT_DIR"] = old


@pytest.fixture
def fixture_project():
    return FIXTURE
