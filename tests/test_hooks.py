import json
import os
import subprocess

import pytest
from conftest import REPO


def test_every_documented_post_tool_use_has_a_logger_route():
    plugin = json.load(open(os.path.join(REPO, ".claude-plugin", "plugin.json"), encoding="utf-8"))
    assert plugin["hooks"] == "./hooks/claude-hooks.json"
    manifest = json.load(open(os.path.join(REPO, "hooks", "claude-hooks.json"), encoding="utf-8"))
    entries = manifest["hooks"]["PostToolUse"]
    routes = {entry["matcher"]: entry["hooks"][0]["command"] for entry in entries}
    assert set(routes) == {"Skill"}
    assert routes["Skill"].count("tt-log.py skill") == 2
    assert manifest["hooks"]["SessionEnd"][0]["hooks"][0]["command"].count("tt-log.py outcome") == 2
    failure = manifest["hooks"]["PostToolUseFailure"][0]
    assert failure["matcher"] == "Bash"
    assert failure["hooks"][0]["command"].count("tt-log.py bash-failure") == 2


def test_codex_hooks_use_the_adapter_and_remain_silent():
    manifest = json.load(open(os.path.join(REPO, "hooks", "hooks.json"), encoding="utf-8"))
    assert set(manifest["hooks"]) == {"SessionStart", "UserPromptSubmit", "PostToolUse", "Stop"}
    for groups in manifest["hooks"].values():
        for group in groups:
            for hook in group["hooks"]:
                assert hook["type"] == "command"
                assert "${CLAUDE_PLUGIN_ROOT}/scripts/tt-codex-hook.py" in hook["command"]
                assert "%CLAUDE_PLUGIN_ROOT%\\scripts\\tt-codex-hook.py" in hook["commandWindows"]
                assert "${PLUGIN_ROOT}" not in hook["command"]
                assert hook["timeout"] == 5


@pytest.mark.skipif(os.name == "nt", reason="Unix hook command requires /bin/sh")
def test_unix_hook_selects_one_available_interpreter_without_retry(tmp_path):
    manifest = json.load(open(os.path.join(REPO, "hooks", "hooks.json"), encoding="utf-8"))
    command = manifest["hooks"]["SessionStart"][0]["hooks"][0]["command"]
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    calls = tmp_path / "calls"

    def interpreter(name, exit_code):
        path = bin_dir / name
        path.write_text(f'#!/bin/sh\nprintf "%s\\n" {name} >> "$CALLS"\nexit {exit_code}\n')
        path.chmod(0o755)

    # A python-only PATH uses the documented fallback exactly once.
    interpreter("python", 0)
    env = {"PATH": str(bin_dir), "CALLS": str(calls), "CLAUDE_PLUGIN_ROOT": str(tmp_path)}
    result = subprocess.run(command, shell=True, executable="/bin/sh", env=env)
    assert result.returncode == 0
    assert calls.read_text().splitlines() == ["python"]

    # Once python3 starts, its failure is authoritative: never retry and duplicate events.
    calls.unlink()
    interpreter("python3", 7)
    result = subprocess.run(command, shell=True, executable="/bin/sh", env=env)
    assert result.returncode == 7
    assert calls.read_text().splitlines() == ["python3"]
