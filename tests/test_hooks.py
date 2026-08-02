import json
import os
import shutil
import subprocess

from conftest import REPO


def test_every_documented_post_tool_use_has_a_logger_route():
    plugin = json.load(open(os.path.join(REPO, ".claude-plugin", "plugin.json"), encoding="utf-8"))
    assert plugin["hooks"] == "./hooks/claude-hooks.json"
    manifest = json.load(open(os.path.join(REPO, "hooks", "claude-hooks.json"), encoding="utf-8"))
    assert set(manifest["hooks"]) == {
        "SessionStart",
        "UserPromptSubmit",
        "SessionEnd",
        "PostToolUse",
        "PostToolUseFailure",
    }
    entries = manifest["hooks"]["PostToolUse"]
    routes = {entry["matcher"]: entry["hooks"][0]["command"] for entry in entries}
    assert set(routes) == {"Bash|Read|Glob|Grep|Skill|Agent|Task|Edit|Write|MultiEdit|mcp__.*"}
    for groups in manifest["hooks"].values():
        for group in groups:
            hook = group["hooks"][0]
            assert hook["command"] == "python3"
            assert hook["args"] == [
                "${CLAUDE_PLUGIN_ROOT}/scripts/tt-codex-hook.py",
                "--client",
                "claude",
            ]
            assert "shell" not in hook and "commandWindows" not in hook
    failure = manifest["hooks"]["PostToolUseFailure"][0]
    assert failure["matcher"] == "Bash"


def test_codex_hooks_use_the_adapter_and_remain_silent():
    manifest = json.load(open(os.path.join(REPO, "hooks", "hooks.json"), encoding="utf-8"))
    assert set(manifest["hooks"]) == {"SessionStart", "UserPromptSubmit", "PostToolUse", "Stop"}
    assert (
        manifest["hooks"]["PostToolUse"][0]["matcher"]
        == "Bash|Read|Glob|Grep|Skill|apply_patch|Edit|Write|mcp__.*"
    )
    for groups in manifest["hooks"].values():
        for group in groups:
            for hook in group["hooks"]:
                assert hook["type"] == "command"
                assert "${CLAUDE_PLUGIN_ROOT}/scripts/tt-codex-hook.py" in hook["command"]
                assert "%CLAUDE_PLUGIN_ROOT%\\scripts\\tt-codex-hook.py" in hook["commandWindows"]
                assert "--client codex" in hook["command"]
                assert "--client codex" in hook["commandWindows"]
                assert "${PLUGIN_ROOT}" not in hook["command"]
                assert hook["timeout"] == 5


def test_claude_hook_exec_form_invokes_one_interpreter_without_retry(tmp_path):
    manifest = json.load(open(os.path.join(REPO, "hooks", "claude-hooks.json"), encoding="utf-8"))
    hook = manifest["hooks"]["SessionStart"][0]["hooks"][0]
    adapter = tmp_path / "adapter.py"
    adapter.write_text("raise SystemExit(7)\n")
    result = subprocess.run(
        [hook["command"], str(adapter)], input="{}", text=True, capture_output=True, check=False
    )
    assert hook["command"] == "python3" and len(hook["args"]) == 3
    assert result.returncode == 7 and result.stdout == "" and result.stderr == ""


def test_codex_hooks_never_block_a_session_on_a_stale_plugin_path(tmp_path):
    """A Codex upgrade leaves persisted hooks pointing at a removed version dir.

    Without a guard the interpreter exits 2 before any of our code runs, and
    Codex treats that as a blocking error on UserPromptSubmit. The logger's own
    fail-open guarantee cannot cover a file that is not there.
    """
    manifest = json.load(open(os.path.join(REPO, "hooks", "hooks.json"), encoding="utf-8"))
    stale = str(tmp_path / "removed-version")
    shell = None if os.name == "nt" else (shutil.which("sh") or "/bin/sh")
    for event, groups in manifest["hooks"].items():
        for group in groups:
            hook = group["hooks"][0]
            assert "[ -f " in hook["command"], event
            assert hook["commandWindows"].startswith("if exist "), event
            if shell:  # the POSIX command needs a POSIX shell to be exercised
                result = subprocess.run(
                    [shell, "-c", hook["command"]],
                    env={**os.environ, "CLAUDE_PLUGIN_ROOT": stale},
                    capture_output=True,
                    text=True,
                    input="{}",
                )
                assert result.returncode == 0, (event, result.stderr)
                assert not result.stderr.strip(), event
