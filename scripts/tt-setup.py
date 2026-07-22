#!/usr/bin/env python3
"""trigger-tree setup — wires the plugin into the current project. Idempotent.

Steps (each reported as created/updated/skipped):
  1. .gitignore: ensure the .trigger-tree entries (data ignored, config committed).
  2. Copy tt-statusline.py to $PROJECT/.claude/tt-statusline.py (plugins cannot ship
     a statusLine, so the script must live in the project).
  3. Register the statusline in $PROJECT/.claude/settings.json (only if none is set).
  4. Create .trigger-tree/config.sh with recognizable truncated prompt previews by
     default. Use --prompt-mode hash|truncate|off to make privacy explicit.

Usage: python3 tt-setup.py [--prompt-mode hash|truncate|off]
"""

import argparse
import json
import os
import re
import stat
import sys
import tempfile

from tt_scope import is_poor_coverage, scan_markdown, suggested_regex

ROOT = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

GITIGNORE_LINES = [".trigger-tree/*", "!.trigger-tree/config.sh"]
# python3-with-fallback so the same registration works on macOS/Linux/Windows(Git Bash)
STATUSLINE_CMD = (
    'python3 "$CLAUDE_PROJECT_DIR"/.claude/tt-statusline.py 2>/dev/null'
    ' || python "$CLAUDE_PROJECT_DIR"/.claude/tt-statusline.py'
)


def report(action, target):
    print(f"{action:8s} {target}")


def assert_safe_destination(path, allow_directory=False):
    """Refuse project-controlled symlinks and non-regular write destinations."""
    root = os.path.abspath(ROOT)
    target = os.path.abspath(path)
    if os.path.commonpath((root, target)) != root:
        raise RuntimeError(f"refusing destination outside project: {path}")
    current = root
    for part in os.path.relpath(target, root).split(os.sep):
        current = os.path.join(current, part)
        if not os.path.lexists(current):
            continue
        mode = os.lstat(current).st_mode
        if stat.S_ISLNK(mode):
            raise RuntimeError(f"refusing symlink destination: {current}")
        if current != target and not stat.S_ISDIR(mode):
            raise RuntimeError(f"refusing non-directory parent: {current}")
        if (
            current == target
            and not stat.S_ISREG(mode)
            and not (allow_directory and stat.S_ISDIR(mode))
        ):
            raise RuntimeError(f"refusing non-regular destination: {current}")


def atomic_write(path, content, mode=0o644):
    """Replace a checked project file without ever following the destination."""
    assert_safe_destination(path)
    parent = os.path.dirname(path)
    assert_safe_destination(parent, allow_directory=True)
    fd, temporary = tempfile.mkstemp(prefix=".trigger-tree-", dir=parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except OSError:
            pass


def ensure_gitignore():
    path = os.path.join(ROOT, ".gitignore")
    assert_safe_destination(path)
    existing = ""
    if os.path.isfile(path):
        existing = open(path, encoding="utf-8").read()
    missing = [ln for ln in GITIGNORE_LINES if ln not in existing.splitlines()]
    if not missing:
        report("skipped", ".gitignore (entries present)")
        return
    if existing and not existing.endswith("\n"):
        existing += "\n"
    atomic_write(path, existing + "\n".join(missing) + "\n")
    report("updated", f".gitignore (+{len(missing)} entries)")


def copy_statusline():
    dst_dir = os.path.join(ROOT, ".claude")
    assert_safe_destination(dst_dir, allow_directory=True)
    os.makedirs(dst_dir, exist_ok=True)
    dst = os.path.join(dst_dir, "tt-statusline.py")
    source = open(os.path.join(SCRIPT_DIR, "tt-statusline.py"), encoding="utf-8").read()
    atomic_write(dst, source, 0o755)
    report("copied", ".claude/tt-statusline.py")


def register_statusline():
    path = os.path.join(ROOT, ".claude", "settings.json")
    assert_safe_destination(path)
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
            report(
                "skipped", ".claude/settings.json (different statusLine present — left untouched)"
            )
        return
    settings["statusLine"] = {
        "type": "command",
        "command": STATUSLINE_CMD,
        "refreshInterval": 5,
    }
    atomic_write(path, json.dumps(settings, indent=2) + "\n")
    report("updated", ".claude/settings.json (statusLine registered)")


def prompt_mode_message(mode):
    if mode == "truncate":
        return "prompt previews: first 200 characters stored locally (gitignored)"
    if mode == "hash":
        return "prompt privacy: hashes only; historical previews unavailable"
    return "prompt privacy: markers only; no text or hash stored"


def choose_prompt_mode(requested, config_exists, stream=None, input_fn=input):
    """Choose once for a new config; never block automation or rewrite an existing choice."""
    if requested:
        return requested, True
    if config_exists:
        return "truncate", False
    stream = stream or sys.stdin
    if not stream.isatty():
        return "truncate", False
    print("Prompt telemetry stays local and gitignored.")
    print("  truncate: recognizable first 200 characters (default)")
    print("  hash: stable fingerprint, no prompt text")
    print("  off: event marker only")
    while True:
        answer = input_fn("Prompt mode [truncate/hash/off]: ").strip().lower()
        aliases = {"": "truncate", "t": "truncate", "h": "hash", "o": "off"}
        answer = aliases.get(answer, answer)
        if answer in ("truncate", "hash", "off"):
            return answer, True
        print("Choose truncate, hash, or off.")


def write_prompt_mode(path, mode):
    assert_safe_destination(path)
    with open(path, encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    assignment = f"TT_LOG_PROMPTS='{mode}'"
    changed = False
    for index, line in enumerate(lines):
        if line.strip().startswith("TT_LOG_PROMPTS="):
            changed = line != assignment
            lines[index] = assignment
            break
    else:
        lines.append(assignment)
        changed = True
    if changed:
        atomic_write(path, "\n".join(lines) + "\n")
    return changed


def write_assignment(path, name, value):
    assert_safe_destination(path)
    lines = open(path, encoding="utf-8").read().splitlines()
    assignment = f"{name}='{value}'"
    for index, line in enumerate(lines):
        if line.strip().startswith(f"{name}="):
            lines[index] = assignment
            break
    else:
        lines.append(assignment)
    atomic_write(path, "\n".join(lines) + "\n")


def effective_watch_regex():
    for path in (
        os.path.join(ROOT, ".trigger-tree", "config.sh"),
        os.path.join(SCRIPT_DIR, "tt-config.sh"),
    ):
        try:
            text = open(path, encoding="utf-8").read()
        except OSError:
            continue
        match = re.search(r"TT_WATCH_REGEX='([^']+)'", text)
        if match:
            return match.group(1)
    return r"(?!)"


def audit_watch_scope(apply_suggestion=False):
    result = scan_markdown(ROOT, effective_watch_regex())
    suffix = f" (scan capped at {result['visited']} files)" if result["capped"] else ""
    print(f"watched: {result['watched']} of {result['markdown']} markdown files{suffix}")
    if not is_poor_coverage(result):
        return
    proposal = suggested_regex(result["paths"])
    if not proposal:
        return
    print(f"suggested TT_WATCH_REGEX: {proposal}")
    if apply_suggestion:
        path = os.path.join(ROOT, ".trigger-tree", "config.sh")
        write_assignment(path, "TT_WATCH_REGEX", proposal)
        report("updated", ".trigger-tree/config.sh (applied suggested TT_WATCH_REGEX)")


def configure_prompts(mode, explicit=False):
    dst_dir = os.path.join(ROOT, ".trigger-tree")
    assert_safe_destination(dst_dir, allow_directory=True)
    os.makedirs(dst_dir, mode=0o700, exist_ok=True)
    os.chmod(dst_dir, 0o700)
    dst = os.path.join(dst_dir, "config.sh")
    if os.path.isfile(dst):
        if explicit and write_prompt_mode(dst, mode):
            report("updated", f".trigger-tree/config.sh ({prompt_mode_message(mode)})")
        else:
            report("skipped", ".trigger-tree/config.sh (existing prompt setting preserved)")
        return
    source = open(os.path.join(SCRIPT_DIR, "tt-config.sh"), encoding="utf-8").read()
    atomic_write(dst, source)
    write_prompt_mode(dst, mode)
    report("created", f".trigger-tree/config.sh ({prompt_mode_message(mode)})")


def parse_args(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt-mode", choices=("truncate", "hash", "off"))
    parser.add_argument("--apply-watch-suggestion", action="store_true")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    config_exists = os.path.isfile(os.path.join(ROOT, ".trigger-tree", "config.sh"))
    prompt_mode, explicit = choose_prompt_mode(args.prompt_mode, config_exists)
    ensure_gitignore()
    copy_statusline()
    register_statusline()
    configure_prompts(prompt_mode, explicit=explicit)
    audit_watch_scope(args.apply_watch_suggestion)
    print("done — restart the session (or wait for settings reload) to activate the statusline")


if __name__ == "__main__":
    main()
