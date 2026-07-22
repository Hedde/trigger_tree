#!/usr/bin/env python3
"""Remove trigger-tree project wiring without deleting telemetry or ignore rules."""

import json
import os
import runpy

ROOT = os.environ.get("TT_PROJECT_DIR") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SETUP = runpy.run_path(os.path.join(SCRIPT_DIR, "tt-setup.py"))
assert_safe_destination = SETUP["assert_safe_destination"]
atomic_write = SETUP["atomic_write"]
report = SETUP["report"]


def unregister_statusline():
    path = os.path.join(ROOT, ".claude", "settings.json")
    assert_safe_destination(path)
    if not os.path.isfile(path):
        report("skipped", ".claude/settings.json (absent)")
        return
    try:
        settings = json.load(open(path, encoding="utf-8"))
    except json.JSONDecodeError:
        report("skipped", ".claude/settings.json (unparseable — remove statusLine manually)")
        return
    status = settings.get("statusLine")
    command = status.get("command", "") if isinstance(status, dict) else ""
    if "tt-statusline.py" not in command:
        report("skipped", ".claude/settings.json (foreign statusLine left untouched)")
        return
    del settings["statusLine"]
    atomic_write(path, json.dumps(settings, indent=2) + "\n")
    report("updated", ".claude/settings.json (trigger-tree statusLine removed)")


def remove_statusline_script():
    path = os.path.join(ROOT, ".claude", "tt-statusline.py")
    assert_safe_destination(path)
    if not os.path.isfile(path):
        report("skipped", ".claude/tt-statusline.py (absent)")
        return
    os.unlink(path)
    report("removed", ".claude/tt-statusline.py")


def main():
    unregister_statusline()
    remove_statusline_script()
    print(
        "kept     .trigger-tree/ telemetry and .gitignore entries; "
        "delete them manually if you want to erase local history"
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"skipped  uninstall ({exc})")
