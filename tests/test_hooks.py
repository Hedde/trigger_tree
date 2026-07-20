import json
import os

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
