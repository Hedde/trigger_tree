#!/usr/bin/env python3
"""trigger-tree setup — wires the plugin into the current project. Idempotent.

Steps (each reported as created/updated/skipped):
  1. .gitignore: ensure the .trigger-tree entries (data ignored, config committed).
  2. Copy tt-statusline.py to $PROJECT/.claude/tt-statusline.py (plugins cannot ship
     a statusLine, so the script must live in the project).
  3. Register the statusline in $PROJECT/.claude/settings.json (only if none is set).
  4. --with-config: copy the default tt-config.sh to .trigger-tree/config.sh so the
     project can customize which paths count as documentation.

Usage: python3 tt-setup.py [--with-config]
"""
import json
import os
import shutil
import sys

ROOT = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

GITIGNORE_LINES = [".trigger-tree/*", "!.trigger-tree/config.sh"]
# python3-with-fallback so the same registration works on macOS/Linux/Windows(Git Bash)
STATUSLINE_CMD = ('python3 "$CLAUDE_PROJECT_DIR"/.claude/tt-statusline.py 2>/dev/null'
                  ' || python "$CLAUDE_PROJECT_DIR"/.claude/tt-statusline.py')


def report(action, target):
    print(f"{action:8s} {target}")


def ensure_gitignore():
    path = os.path.join(ROOT, ".gitignore")
    existing = ""
    if os.path.isfile(path):
        existing = open(path, encoding="utf-8").read()
    missing = [ln for ln in GITIGNORE_LINES if ln not in existing.splitlines()]
    if not missing:
        report("skipped", ".gitignore (entries present)")
        return
    with open(path, "a", encoding="utf-8") as fh:
        if existing and not existing.endswith("\n"):
            fh.write("\n")
        fh.write("\n".join(missing) + "\n")
    report("updated", f".gitignore (+{len(missing)} entries)")


def copy_statusline():
    dst_dir = os.path.join(ROOT, ".claude")
    os.makedirs(dst_dir, exist_ok=True)
    dst = os.path.join(dst_dir, "tt-statusline.py")
    shutil.copyfile(os.path.join(SCRIPT_DIR, "tt-statusline.py"), dst)
    os.chmod(dst, 0o755)
    report("copied", ".claude/tt-statusline.py")


def register_statusline():
    path = os.path.join(ROOT, ".claude", "settings.json")
    settings = {}
    if os.path.isfile(path):
        try:
            settings = json.load(open(path, encoding="utf-8"))
        except json.JSONDecodeError:
            report("skipped", ".claude/settings.json (unparseable — register statusLine manually)")
            return
    if "statusLine" in settings:
        if settings["statusLine"].get("command", "").endswith("tt-statusline.py"):
            report("skipped", ".claude/settings.json (statusLine already registered)")
        else:
            report("skipped", ".claude/settings.json (different statusLine present — left untouched)")
        return
    settings["statusLine"] = {
        "type": "command",
        "command": STATUSLINE_CMD,
        "refreshInterval": 5,
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(settings, fh, indent=2)
        fh.write("\n")
    report("updated", ".claude/settings.json (statusLine registered)")


def copy_config():
    dst_dir = os.path.join(ROOT, ".trigger-tree")
    os.makedirs(dst_dir, exist_ok=True)
    dst = os.path.join(dst_dir, "config.sh")
    if os.path.isfile(dst):
        report("skipped", ".trigger-tree/config.sh (already exists)")
        return
    shutil.copyfile(os.path.join(SCRIPT_DIR, "tt-config.sh"), dst)
    report("created", ".trigger-tree/config.sh (project override)")


def main():
    ensure_gitignore()
    copy_statusline()
    register_statusline()
    if "--with-config" in sys.argv:
        copy_config()
    print("done — restart the session (or wait for settings reload) to activate the statusline")


if __name__ == "__main__":
    main()
