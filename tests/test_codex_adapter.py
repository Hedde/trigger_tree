import io
import json
import os
import runpy
import subprocess
import sys

import pytest
from conftest import REPO, load_script


def test_translate_codex_lifecycle_and_tool_payloads(tmp_path, monkeypatch):
    mod = load_script("tt-codex-hook.py", tmp_path)

    route, session = mod.translate({"hook_event_name": "SessionStart"})
    assert route == "session" and session["source"] == "codex"
    assert mod.translate({"hook_event_name": "UserPromptSubmit"})[0] == "prompt"
    monkeypatch.setenv("PLUGIN_ROOT", str(tmp_path))
    route, stop = mod.translate({"hook_event_name": "Stop"})
    assert route == "outcome" and stop["reason"] == "codex-stop"
    monkeypatch.delenv("PLUGIN_ROOT")
    assert mod.translate({"hook_event_name": "Stop"})[0] is None
    assert mod.translate({"hook_event_name": "Unknown"})[0] is None

    route, bash = mod.translate(
        {"hook_event_name": "PostToolUse", "tool_name": "Bash", "tool_input": {"cmd": "pwd"}}
    )
    assert route == "bash" and bash["tool_input"]["command"] == "pwd"
    route, native_read = mod.translate(
        {"hook_event_name": "PostToolUse", "tool_name": "Read", "tool_input": None}
    )
    assert route == "read" and native_read["tool_input"] == {}
    assert (
        mod.translate(
            {"hook_event_name": "PostToolUse", "tool_name": "Skill", "tool_input": {"skill": "tt"}}
        )[0]
        == "skill"
    )
    assert mod.translate({"hook_event_name": "PostToolUseFailure", "tool_name": "Bash"})[0] == (
        "bash-failure"
    )
    assert mod.translate({"hook_event_name": "PostToolUseFailure", "tool_name": "Read"})[0] is None
    route, ended = mod.translate({"hook_event_name": "SessionEnd"})
    assert route == "outcome" and ended["reason"] == "claude-session-end"

    route, read = mod.translate(
        {
            "hook_event_name": "PostToolUse",
            "tool_name": "mcp__filesystem__read_file",
            "tool_input": {"path": "docs/a.md"},
        }
    )
    assert route == "read" and read["tool_name"] == "Read"
    assert read["tool_input"] == {"file_path": "docs/a.md"}

    route, search = mod.translate(
        {
            "hook_event_name": "PostToolUse",
            "tool_name": "mcp__filesystem__search_files",
            "tool_input": {"path": "docs"},
        }
    )
    assert route == "read" and search["tool_name"] == "Grep"
    assert search["tool_input"] == {"path": "docs"}


@pytest.mark.parametrize(
    "payload",
    [
        {"hook_event_name": "PostToolUse", "tool_name": "update_plan", "tool_input": {}},
        {"hook_event_name": "PostToolUse", "tool_name": "mcp__web__read", "tool_input": {}},
        {
            "hook_event_name": "PostToolUse",
            "tool_name": "mcp__web__read",
            "tool_input": {"uri": "https://example.com"},
        },
    ],
)
def test_translate_ignores_non_file_tools(payload, tmp_path):
    mod = load_script("tt-codex-hook.py", tmp_path)
    assert mod.translate(payload)[0] is None


def test_payload_and_project_root_fallbacks(tmp_path, monkeypatch):
    mod = load_script("tt-codex-hook.py", tmp_path)
    assert mod.read_payload(io.StringIO("[]")) == {}
    assert mod.read_payload(io.StringIO("bad")) == {}

    result = type("Result", (), {"stdout": ""})()
    monkeypatch.setattr(mod.subprocess, "run", lambda *args, **kwargs: result)
    assert mod.project_root(str(tmp_path)) == str(tmp_path)
    monkeypatch.setattr(
        mod.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(subprocess.SubprocessError()),
    )
    assert mod.project_root(str(tmp_path)) == str(tmp_path)


def test_main_delegates_silently_and_restores_process_state(tmp_path, monkeypatch):
    mod = load_script("tt-codex-hook.py", tmp_path)
    payload = {
        "hook_event_name": "UserPromptSubmit",
        "session_id": "codex-session",
        "cwd": str(tmp_path),
        "prompt": "inspect docs",
    }
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    original_argv, original_stdin = sys.argv, sys.stdin
    monkeypatch.setenv("TT_PROJECT_DIR", "before")
    called = {}

    def fake_run(path, run_name):
        called.update(path=path, run_name=run_name, argv=list(sys.argv), stdin=sys.stdin.read())
        raise SystemExit(0)

    monkeypatch.setattr(mod.runpy, "run_path", fake_run)
    mod.main()

    assert called["path"].endswith("tt-log.py") and called["run_name"] == "__main__"
    assert called["argv"][-1] == "prompt"
    assert json.loads(called["stdin"])["session_id"] == "codex-session"
    assert sys.argv is original_argv and sys.stdin is original_stdin
    assert os.environ["TT_PROJECT_DIR"] == "before"


def test_main_removes_temporary_project_root(tmp_path, monkeypatch):
    mod = load_script("tt-codex-hook.py", tmp_path)
    monkeypatch.delenv("TT_PROJECT_DIR", raising=False)
    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO(json.dumps({"hook_event_name": "UserPromptSubmit", "cwd": str(tmp_path)})),
    )
    monkeypatch.setattr(mod.runpy, "run_path", lambda *args, **kwargs: None)
    mod.main()
    assert "TT_PROJECT_DIR" not in os.environ


def test_real_codex_hook_logs_unified_exec_read_at_repo_root(tmp_path):
    docs = tmp_path / "docs"
    nested = tmp_path / "src" / "nested"
    docs.mkdir()
    nested.mkdir(parents=True)
    target = docs / "guide.md"
    target.write_text("guide")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    payload = {
        "hook_event_name": "PostToolUse",
        "session_id": "codex-session",
        "cwd": str(nested),
        "tool_name": "Bash",
        "tool_input": {"cmd": f'cat "{target}"'},
    }
    result = subprocess.run(
        [sys.executable, os.path.join(REPO, "scripts", "tt-codex-hook.py")],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0 and result.stdout == "" and result.stderr == ""
    history = tmp_path / ".trigger-tree" / "history.jsonl"
    event = json.loads(history.read_text().strip())
    assert (event["t"], event["path"], event["session"]) == (
        "read",
        "docs/guide.md",
        "codex-session",
    )


def test_script_entrypoint_swallows_bad_input(monkeypatch):
    script = os.path.join(REPO, "scripts", "tt-codex-hook.py")
    monkeypatch.setattr(sys, "stdin", io.StringIO("not-json"))
    with pytest.raises(SystemExit, match="0"):
        runpy.run_path(script, run_name="__main__")
