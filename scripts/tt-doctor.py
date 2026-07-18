#!/usr/bin/env python3
"""Explain whether trigger-tree is installed and receiving usable telemetry."""

import json
import os
import sys

ROOT = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None


def history_health():
    path = os.path.join(ROOT, ".trigger-tree", "history.jsonl")
    if not os.path.isfile(path):
        return "WARN", "telemetry: no history yet — start a fresh session and read a doc"
    valid = 0
    latest = None
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(event, dict) and event.get("t"):
                    valid += 1
                    latest = event.get("ts") or latest
    except OSError:
        return "FAIL", "telemetry: history exists but cannot be read"
    if not valid:
        return "FAIL", "telemetry: history contains no valid events"
    suffix = f", latest {latest}" if latest else ""
    return "PASS", f"telemetry: {valid} valid events{suffix}"


def hooks_health():
    manifest = load_json(os.path.join(PLUGIN_ROOT, "hooks", "hooks.json"))
    hooks = manifest.get("hooks", {}) if isinstance(manifest, dict) else {}
    expected = {"SessionStart", "UserPromptSubmit", "PostToolUse"}
    if expected.issubset(hooks):
        return "PASS", "plugin hooks: session, prompt, read/search, and skill telemetry registered"
    return "FAIL", "plugin hooks: manifest missing or incomplete — reinstall the plugin"


def ignore_health():
    path = os.path.join(ROOT, ".gitignore")
    try:
        lines = open(path, encoding="utf-8").read().splitlines()
    except OSError:
        lines = []
    ignored = ".trigger-tree/" in lines or ".trigger-tree/*" in lines
    if ignored:
        return "PASS", "privacy: telemetry directory is gitignored"
    return "FAIL", "privacy: .trigger-tree is not gitignored — run /tt setup"


def statusline_health():
    script = os.path.join(ROOT, ".claude", "tt-statusline.py")
    settings = load_json(os.path.join(ROOT, ".claude", "settings.json"))
    status = settings.get("statusLine", {}) if isinstance(settings, dict) else {}
    command = status.get("command", "") if isinstance(status, dict) else ""
    if os.path.isfile(script) and "tt-statusline.py" in command:
        return "PASS", "statusline: installed and registered"
    return "WARN", "statusline: not fully wired (telemetry still works) — run /tt setup"


def main():
    checks = [hooks_health(), ignore_health(), statusline_health(), history_health()]
    print("🌳 trigger-tree doctor")
    for state, message in checks:
        icon = {"PASS": "✓", "WARN": "!", "FAIL": "✗"}[state]
        print(f"{icon} {message}")
    failures = sum(state == "FAIL" for state, _ in checks)
    warnings = sum(state == "WARN" for state, _ in checks)
    if failures:
        print(f"attention needed — {failures} failed, {warnings} warnings")
    elif warnings:
        plural = "s" if warnings != 1 else ""
        print(f"telemetry healthy — {warnings} optional setup warning{plural}")
    else:
        print("all checks passed — telemetry is wired and receiving events")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
