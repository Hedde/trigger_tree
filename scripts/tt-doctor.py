#!/usr/bin/env python3
"""Explain whether trigger-tree is installed and receiving usable telemetry."""

import glob
import json
import os
import re
import sys
import time
from datetime import datetime

from tt_scope import is_poor_coverage, scan_markdown

ROOT = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA_VERSION = 1
SUPPORTED_PYTHON = (3, 10), (3, 13)


def load_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None


def history_health():
    paths = sorted(glob.glob(os.path.join(ROOT, ".trigger-tree", "history*.jsonl")))
    if not paths:
        return "WARN", "telemetry: no history yet — start a fresh session and read a doc"
    valid = corrupt = legacy = future = 0
    latest = None
    try:
        for path in paths:
            with open(path, encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        corrupt += 1
                        continue
                    if not isinstance(event, dict) or not event.get("t"):
                        corrupt += 1
                        continue
                    version = event.get("schema_version", 0)
                    if version == 0:
                        legacy += 1
                    elif version != SCHEMA_VERSION:
                        future += 1
                        continue
                    valid += 1
                    latest = event.get("ts") or latest
    except OSError:
        return "FAIL", "telemetry: history exists but cannot be read"
    if future:
        return (
            "FAIL",
            f"telemetry: {future} event(s) use a newer schema — update trigger-tree before reading this history",
        )
    if not valid:
        return (
            "FAIL",
            "telemetry: history contains no usable events — move corrupt logs aside or restart telemetry",
        )
    suffix = f", latest {latest}" if latest else ""
    rotation = f", {len(paths) - 1} rotated file(s) included" if len(paths) > 1 else ""
    migration = f", {legacy} legacy event(s) migrated" if legacy else ""
    if corrupt:
        return (
            "WARN",
            f"telemetry: {valid} usable events{suffix}{rotation}{migration}; {corrupt} corrupt line(s) ignored — inspect history*.jsonl",
        )
    return "PASS", f"telemetry: {valid} usable events{suffix}{rotation}{migration}"


def hooks_health():
    claude_manifest = load_json(os.path.join(PLUGIN_ROOT, "hooks", "claude-hooks.json"))
    hooks = claude_manifest.get("hooks", {}) if isinstance(claude_manifest, dict) else {}
    commands = json.dumps(claude_manifest) if claude_manifest else ""
    claude_ok = {
        "SessionStart",
        "UserPromptSubmit",
        "PostToolUse",
        "PostToolUseFailure",
        "SessionEnd",
    }.issubset(hooks) and all(
        marker in commands
        for marker in (
            "Bash",
            "Read",
            "Glob",
            "Grep",
            "Skill",
            "tt-codex-hook.py",
            "--client",
            "claude",
        )
    )
    codex_manifest = load_json(os.path.join(PLUGIN_ROOT, "hooks", "hooks.json"))
    codex_hooks = codex_manifest.get("hooks", {}) if isinstance(codex_manifest, dict) else {}
    codex_commands = json.dumps(codex_manifest) if codex_manifest else ""
    codex_ok = {"SessionStart", "UserPromptSubmit", "PostToolUse", "Stop"}.issubset(
        codex_hooks
    ) and all(
        marker in codex_commands
        for marker in ("tt-codex-hook.py", "CLAUDE_PLUGIN_ROOT", "--client codex")
    )
    if claude_ok and codex_ok:
        return "PASS", "plugin hook files: Claude Code and Codex routes are intact"
    return "FAIL", "plugin hook files: missing logger routes — reinstall the plugin"


def watch_regex():
    for path in (
        os.path.join(ROOT, ".trigger-tree", "config.sh"),
        os.path.join(PLUGIN_ROOT, "scripts", "tt-config.sh"),
    ):
        try:
            text = open(path, encoding="utf-8").read()
        except OSError:
            continue
        match = re.search(r"TT_WATCH_REGEX='([^']+)'", text)
        if match:
            return match.group(1)
    return r"(?!)"


def coverage_health():
    result = scan_markdown(ROOT, watch_regex())
    summary = f"coverage: {result['watched']} of {result['markdown']} markdown files watched"
    remediation = "set TT_WATCH_REGEX in .trigger-tree/config.sh"
    if result["markdown"] and result["watched"] == 0:
        return "FAIL", f"{summary} — {remediation}"
    if is_poor_coverage(result):
        return "WARN", f"{summary} (very low) — {remediation}"
    return "PASS", summary


def _lifecycle_events():
    events = []
    for path in sorted(glob.glob(os.path.join(ROOT, ".trigger-tree", "history*.jsonl"))):
        try:
            lines = open(path, encoding="utf-8", errors="replace")
        except OSError:
            continue
        with lines:
            for line in lines:
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(event, dict) and event.get("t") in ("session", "read"):
                    events.append(event)
    return events


def liveness_health():
    events = _lifecycle_events()
    current = os.environ.get("CLAUDE_SESSION_ID")
    if current:
        if any(event.get("t") == "session" and event.get("session") == current for event in events):
            return "PASS", "hook liveness: current session start was recorded"
        return (
            "FAIL",
            "hook liveness: current session start is absent — check /hooks, restart the session, then reinstall the plugin if still absent",
        )
    state_paths = glob.glob(os.path.join(ROOT, ".trigger-tree", "sessions", "*.json"))
    newest_state = max((os.path.getmtime(path) for path in state_paths), default=0)
    timestamps = []
    for event in events:
        try:
            timestamps.append(
                datetime.fromisoformat(event.get("ts", "").replace("Z", "+00:00")).timestamp()
            )
        except (AttributeError, TypeError, ValueError):
            pass
    newest = max(timestamps + [newest_state], default=0)
    if not newest:
        return (
            "WARN",
            "hook liveness: no hook events have ever been recorded — run /tt setup and start a fresh session",
        )
    age_days = max(0, int((time.time() - newest) / 86400))
    if age_days > 7:
        return (
            "WARN",
            f"hook liveness: events exist but are stale ({age_days} days) — informational; start a fresh session to verify",
        )
    return "PASS", "hook liveness: recent session/read activity found"


def config_health():
    path = os.path.join(ROOT, ".trigger-tree", "config.sh")
    if not os.path.isfile(path):
        return "PASS", "config: defaults valid (no project override)"
    try:
        text = open(path, encoding="utf-8").read()
    except OSError:
        return "FAIL", "config: project override cannot be read — fix permissions or remove it"
    assignments = dict(re.findall(r"(?m)^(TT_[A-Z_]+)='([^']*)'\s*$", text))
    malformed = [
        line.strip()
        for line in text.splitlines()
        if line.strip().startswith("TT_") and not re.match(r"^TT_[A-Z_]+='[^']*'\s*$", line.strip())
    ]
    if malformed:
        return "FAIL", f"config: unparseable assignment `{malformed[0]}` — use KEY='value'"
    for name in ("TT_WATCH_REGEX", "TT_SCAN_REGEX", "TT_ALWAYS_LOADED_REGEX"):
        if name in assignments:
            try:
                re.compile(assignments[name])
            except re.error as exc:
                return "FAIL", f"config: {name} is invalid ({exc}) — fix the regex"
    prompt_mode = assignments.get("TT_LOG_PROMPTS")
    if prompt_mode is not None and prompt_mode not in ("hash", "truncate", "off"):
        return "FAIL", "config: TT_LOG_PROMPTS must be hash, truncate, or off"
    experimental = assignments.get("TT_EXPERIMENTAL_OUTCOMES")
    if experimental is not None and experimental not in ("on", "off"):
        return "FAIL", "config: TT_EXPERIMENTAL_OUTCOMES must be on or off"
    rotate = assignments.get("TT_ROTATE_BYTES")
    if rotate is not None:
        try:
            if int(rotate) <= 0:
                raise ValueError
        except ValueError:
            return "FAIL", "config: TT_ROTATE_BYTES must be a positive integer"
    return "PASS", "config: project override parses and validates"


def python_health():
    current = sys.version_info[:2]
    if SUPPORTED_PYTHON[0] <= current <= SUPPORTED_PYTHON[1]:
        return "PASS", f"python: {current[0]}.{current[1]} is supported (3.10–3.13)"
    return "FAIL", f"python: {current[0]}.{current[1]} unsupported — configure Python 3.10–3.13"


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
    checks = [
        hooks_health(),
        liveness_health(),
        config_health(),
        coverage_health(),
        python_health(),
        ignore_health(),
        statusline_health(),
        history_health(),
    ]
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
