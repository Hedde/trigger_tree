import importlib.util
import os
import sys

import pytest
from conftest import REPO

spec = importlib.util.spec_from_file_location(
    "trigger_tree_cli", os.path.join(REPO, "trigger_tree", "cli.py")
)
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)


def test_help_prints_usage_and_succeeds(capsys):
    assert cli.main(["--help"]) == 0
    assert "usage: tt <" in capsys.readouterr().out


def test_missing_and_unknown_subcommands_fail_with_usage(capsys):
    assert cli.main([]) == 2
    assert cli.main(["frobnicate"]) == 2
    err = capsys.readouterr().err
    assert err.count("usage: tt <") == 2


def test_script_path_prefers_the_bundled_wheel_copy(tmp_path):
    bundled = tmp_path / "_scripts"
    bundled.mkdir()
    (bundled / "tt-doctor.py").write_text("", encoding="utf-8")
    assert cli.script_path("doctor", tmp_path) == bundled / "tt-doctor.py"
    repo_fallback = cli.script_path("doctor")
    assert repo_fallback == cli.script_path("doctor", os.path.join(REPO, "trigger_tree"))
    assert str(repo_fallback).endswith(os.path.join("scripts", "tt-doctor.py"))


def test_dispatch_runs_doctor_against_the_project(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.setattr(sys, "argv", ["tt"])
    with pytest.raises(SystemExit):
        cli.main(["doctor"])
    assert "trigger-tree doctor" in capsys.readouterr().out


def test_dispatch_passes_arguments_through(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.setattr(sys, "argv", ["tt"])
    try:
        assert cli.main(["stats", "--badge"]) == 0
    except SystemExit as exc:  # a script may exit explicitly; both are acceptable
        assert not exc.code
    assert (tmp_path / ".trigger-tree" / "badge.json").is_file()
