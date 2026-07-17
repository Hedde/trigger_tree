import json
import os

from conftest import REPO


def test_every_documented_post_tool_use_has_a_logger_route():
    manifest = json.load(open(os.path.join(REPO, "hooks", "hooks.json"), encoding="utf-8"))
    entries = manifest["hooks"]["PostToolUse"]
    routes = {entry["matcher"]: entry["hooks"][0]["command"] for entry in entries}
    assert set(routes) == {"Read|Glob|Grep", "Skill", "Bash"}
    assert routes["Read|Glob|Grep"].count("tt-log.py read") == 2
    assert routes["Skill"].count("tt-log.py skill") == 2
    assert routes["Bash"].count("tt-log.py bash") == 2
