"""Regressions for Draciste's installed-package audit (#50 and #51)."""

import io
import json
import os
import stat
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

import pytest
from conftest import REPO, load_script


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


@pytest.mark.parametrize("mode", ["off", "hash", "truncate", "invalid"])
def test_noninteractive_setup_preserves_user_privacy(tmp_path, monkeypatch, mode):
    config = tmp_path / "user.sh"
    config.write_text(f"TT_LOG_PROMPTS='{mode}'\n")
    monkeypatch.setenv("TT_USER_CONFIG", str(config))
    mod = load_script("tt-setup.py", tmp_path)
    mod.main([])
    expected = mode if mode != "invalid" else "hash"
    assert f"TT_LOG_PROMPTS='{expected}'" in (tmp_path / ".trigger-tree/config.sh").read_text()


def test_effective_ignore_rules_negation_tracking_and_global_excludes(tmp_path):
    git(tmp_path, "init")
    git(tmp_path, "config", "core.excludesFile", os.devnull)
    mod = load_script("tt-doctor.py", tmp_path)
    ignore = tmp_path / ".gitignore"
    ignore.write_text(".trigger-tree/*\n!.trigger-tree/config.sh\n")
    assert mod.ignore_health()[0] == "PASS"
    ignore.write_text(ignore.read_text() + "!.trigger-tree/history.jsonl\n")
    assert mod.ignore_health()[0] == "FAIL"
    ignore.unlink()
    excludes = tmp_path / "global-ignore"
    excludes.write_text(".trigger-tree/*\n")
    git(tmp_path, "config", "core.excludesFile", str(excludes))
    assert mod.ignore_health()[0] == "PASS"
    history = tmp_path / ".trigger-tree/history.jsonl"
    history.parent.mkdir()
    history.write_text("{}\n")
    git(tmp_path, "add", "-f", ".trigger-tree/history.jsonl")
    assert mod.ignore_health()[0] == "FAIL"
    git(tmp_path, "rm", "--cached", ".trigger-tree/history.jsonl")
    (history.parent / "other-private.txt").write_text("synthetic")
    ignore.write_text("!.trigger-tree/other-private.txt\n")
    assert mod.ignore_health()[0] == "FAIL"


def test_doctor_cannot_verify_without_git(tmp_path, monkeypatch):
    mod = load_script("tt-doctor.py", tmp_path)
    monkeypatch.setattr(mod.subprocess, "run", lambda *a, **kw: (_ for _ in ()).throw(OSError()))
    assert mod.ignore_health()[0] == "WARN"


def test_doctor_and_stats_reject_incomplete_read(tmp_path):
    history = tmp_path / ".trigger-tree/history.jsonl"
    history.parent.mkdir()
    history.write_text('{"t":"read","schema_version":1}\n')
    assert load_script("tt-doctor.py", tmp_path).history_health()[0] == "FAIL"
    assert load_script("tt-stats.py", tmp_path).load_events([history]) == []


def test_multi_path_call_retains_both_paths_and_deduplicates_retries(tmp_path):
    events = [
        dict(t="read", path=path, session="s", tool_use_id="call", schema_version=1)
        for path in ("docs/a.md", "docs/b.md")
    ]
    history = tmp_path / "history.jsonl"
    history.write_text("\n".join(json.dumps(e) for e in events * 2))
    actual = load_script("tt-stats.py", tmp_path).load_events([history])
    assert [e["path"] for e in actual] == ["docs/a.md", "docs/b.md"]


@pytest.mark.parametrize(
    "response,expected",
    [
        ({"exit_code": 1}, "fail"),
        ({"exit_code": 0}, "pass"),
        ({"exitCode": -1}, "fail"),
        ({"is_error": True}, "fail"),
        ({"exit_code": True}, "unknown"),
        ({}, "unknown"),
        ("Process exited with code 1\nsynthetic failure", "fail"),
        ("Exit code: 0", "pass"),
        ("unstructured", "unknown"),
        (None, "unknown"),
    ],
)
def test_codex_test_outcomes_are_observed(tmp_path, monkeypatch, response, expected):
    monkeypatch.setenv("TT_PROJECT_DIR", str(tmp_path))
    mod = load_script("tt-log.py", tmp_path)
    data = dict(
        client="codex",
        session_id="s",
        tool_use_id="call",
        tool_name="Bash",
        tool_input={"command": "pytest"},
        tool_response=response,
    )
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(data)))
    monkeypatch.setattr(sys, "argv", ["tt-log.py", "bash"])
    mod.main()
    events = [
        json.loads(line)
        for line in (tmp_path / ".trigger-tree/history.jsonl").read_text().splitlines()
    ]
    assert next(e for e in events if e["t"] == "test")["status"] == expected
    assert mod.session_signals("s")[1] == expected


def test_apply_patch_command_and_unknown_mcp_write(tmp_path, monkeypatch):
    monkeypatch.setenv("TT_PROJECT_DIR", str(tmp_path))
    mod = load_script("tt-log.py", tmp_path)
    assert mod.edit_paths(
        {"command": "*** Begin Patch\n*** Update File: docs/a.md\n*** End Patch"}
    ) == ["docs/a.md"]
    adapter = load_script("tt-codex-hook.py", tmp_path)
    assert (
        adapter.normalize_tool(
            dict(tool_name="mcp__synthetic__write_file", tool_input={"path": "docs/a.md"})
        )[0]
        is None
    )
    for target in (None, "https://example.org/file"):
        assert (
            adapter.normalize_tool(
                dict(tool_name="mcp__filesystem__read_file", tool_input={"path": target})
            )[0]
            is None
        )


def test_git_root_explicit_utf8(tmp_path, monkeypatch):
    mod = load_script("tt_runtime.py", tmp_path)
    monkeypatch.delenv("TT_PROJECT_DIR", raising=False)
    root = str(tmp_path / "Žluťoučký-漢字")

    def run(*args, **kwargs):
        assert kwargs["encoding"] == "utf-8"
        return SimpleNamespace(stdout=root + "\n")

    monkeypatch.setattr(mod.subprocess, "run", run)
    assert mod.project_root(str(tmp_path)) == root


@pytest.mark.parametrize("script", ["tt-log.py", "tt-setup.py", "tt-report.py", "tt-stats.py"])
def test_reparse_point_is_rejected_before_writes(tmp_path, monkeypatch, script):
    monkeypatch.setenv("TT_PROJECT_DIR", str(tmp_path))
    directory = tmp_path / ".trigger-tree"
    directory.mkdir()
    mod = load_script(script, tmp_path)
    original = os.lstat

    def lstat(path, *args, **kwargs):
        if os.fspath(path) == str(directory):
            return SimpleNamespace(st_mode=stat.S_IFDIR | 0o755, st_file_attributes=0x400)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(os, "lstat", lstat)
    if script == "tt-log.py":
        mod.append({"t": "session"}, 10000)
    else:
        with pytest.raises(RuntimeError):
            if script == "tt-setup.py":
                mod.assert_safe_destination(directory / "config.sh")
            elif script == "tt-report.py":
                mod.write_report("private")
            else:
                mod.write_badge({})
    assert list(directory.iterdir()) == []


@pytest.mark.skipif(os.name != "nt", reason="Windows junction regression")
def test_native_windows_junction_never_receives_telemetry(tmp_path, monkeypatch):
    root = tmp_path / "project"
    root.mkdir()
    target = tmp_path / "target"
    target.mkdir()
    subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(root / ".trigger-tree"), str(target)],
        check=True,
        capture_output=True,
    )
    monkeypatch.setenv("TT_PROJECT_DIR", str(root))
    load_script("tt-log.py", root).append({"t": "session"}, 10000)
    with pytest.raises(RuntimeError):
        load_script("tt-setup.py", root).assert_safe_destination(root / ".trigger-tree/config.sh")
    with pytest.raises(RuntimeError):
        load_script("tt-report.py", root).write_report("private")
    assert list(target.iterdir()) == []


def test_packaged_launcher_and_legacy_console(tmp_path):
    archive = tmp_path / "plugin.zip"
    subprocess.run(
        [
            sys.executable,
            str(Path(REPO) / ".github/scripts/build_codex_zip.py"),
            "--output",
            str(archive),
        ],
        check=True,
        capture_output=True,
    )
    package = tmp_path / "plugin"
    with ZipFile(archive) as zipped:
        zipped.extractall(package)
    env = {
        **os.environ,
        "TT_OPEN_DRYRUN": "1",
        "TT_PROJECT_DIR": str(tmp_path),
        "PYTHONIOENCODING": "cp1250",
    }
    result = subprocess.run(
        ["bash", str(package / "scripts/tt-open.sh"), "demo"], env=env, capture_output=True
    )
    assert result.returncode == 0, result.stderr
    result = subprocess.run(
        [sys.executable, str(package / "scripts/tt-tips.py"), "--client", "codex"],
        env=env,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr
    # The module's version lookup must work using just the Codex archive layout.
    report = load_script("tt-report.py", tmp_path)
    report.SCRIPT_DIR = str(package / "scripts")
    assert (
        report.plugin_version()
        == json.loads((package / ".codex-plugin/plugin.json").read_text())["version"]
    )


def test_console_output_escapes_unencodable_path(tmp_path, monkeypatch):
    mod = load_script("tt_runtime.py", tmp_path)
    output = io.BytesIO()
    stream = io.TextIOWrapper(output, encoding="cp1250")
    monkeypatch.setattr(sys, "stdout", stream)
    mod.emit(str(tmp_path / "漢字"))
    stream.flush()
    assert b"\\u6f22\\u5b57" in output.getvalue()
