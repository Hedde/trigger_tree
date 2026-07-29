#!/usr/bin/env python3
"""Explain whether trigger-tree is installed and receiving usable telemetry."""

import glob
import json
import os
import re
import sys
import time
from datetime import datetime

import tt_adherence
from tt_runtime import session_id, user_config_path
from tt_scope import is_poor_coverage, parse_ignore, scan_markdown, symlinked_surfaces

ROOT = os.environ.get("TT_PROJECT_DIR") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA_VERSION = 1
SUPPORTED_PYTHON = (3, 10), (3, 14)
MANIFEST_PATH = os.path.join(ROOT, ".trigger-tree", "directives.json")


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


def codex_trust_health():
    """Codex silently skips hooks without a persisted trust decision (issue #11).

    Only the presence of trust entries in $CODEX_HOME/config.toml is observable;
    the trusted hashes are Codex-internal, so a hook changed by an upgrade still
    needs re-review in the Codex TUI even when this check passes.
    """
    home = os.environ.get("CODEX_HOME") or os.path.expanduser("~/.codex")
    try:
        text = open(os.path.join(home, "config.toml"), encoding="utf-8").read()
    except OSError:
        return None
    plugin = re.search(r'(?ms)^\[plugins\."trigger-tree@[^"]*"\]\n(.*?)(?=^\[|\Z)', text)
    if not plugin or not re.search(r"(?m)^enabled\s*=\s*true", plugin.group(1)):
        return None
    trusted = set(
        re.findall(r'(?m)^\[hooks\.state\."trigger-tree@[^"]*:([a-z_]+):\d+:\d+"\]', text)
    )
    expected = {"session_start", "user_prompt_submit", "post_tool_use", "stop"}
    missing = sorted(expected - trusted)
    if len(missing) == len(expected):
        return (
            "WARN",
            "codex trust: hooks are installed but not trusted — open the Codex TUI once and"
            " choose 'Trust all and continue'; non-interactive codex exec never persists trust",
        )
    if missing:
        return (
            "WARN",
            f"codex trust: {len(expected) - len(missing)} of {len(expected)} hooks trusted"
            f" ({', '.join(missing)} pending) — re-review hooks in the Codex TUI",
        )
    return (
        "PASS",
        "codex trust: all 4 hooks have a persisted trust decision — an upgrade that changes"
        " a hook triggers a new review",
    )


def agents_health():
    """Report persona definitions whose usage cannot currently be observed.

    Every definition's description sits in the system prompt on each request,
    so an unused persona is recurring cost in the same way an untriggered
    directive is. Silence only means that once capture is on.
    """
    defined = []
    for base in (".claude/agents", "agents"):
        top = os.path.join(ROOT, *base.split("/"))
        if not os.path.isdir(top) or os.path.islink(top):
            continue
        defined += [name for name in sorted(os.listdir(top)) if name.endswith(".md")]
    if not defined:
        return None
    enabled, _ = _effective_config("TT_LOG_AGENTS", "off")
    if enabled != "on":
        return (
            "WARN",
            f"agents: {len(defined)} persona definition(s) found but agent capture is off"
            " — run /tt setup to record which personas are actually used; until then"
            " never-invoked cannot be distinguished from never-observed",
        )
    return "PASS", f"agents: {len(defined)} persona definition(s), capture on"


def watch_regex():
    for path in (
        os.path.join(ROOT, ".trigger-tree", "config.sh"),
        user_config_path(),
        os.path.join(PLUGIN_ROOT, "scripts", "tt-config.sh"),
    ):
        try:
            text = open(path, encoding="utf-8").read()
        except OSError:
            continue
        match = re.search(r"(?m)^TT_WATCH_REGEX='([^']+)'", text)
        if match:
            return match.group(1)
    return r"(?!)"


def scope_ignore():
    for path in (
        os.path.join(ROOT, ".trigger-tree", "config.sh"),
        user_config_path(),
        os.path.join(PLUGIN_ROOT, "scripts", "tt-config.sh"),
    ):
        try:
            text = open(path, encoding="utf-8").read()
        except OSError:
            continue
        match = re.search(r"(?m)^TT_SCOPE_IGNORE='([^']*)'", text)
        if match:
            return parse_ignore(match.group(1))
    return ()


def surfaces_health():
    """Name watched surfaces hidden behind a directory symlink (issue #15)."""
    surfaces = symlinked_surfaces(ROOT, watch_regex())
    if not surfaces:
        return None
    names = ", ".join(item["path"] for item in surfaces[:3])
    suffix = "…" if len(surfaces) > 3 else ""
    return "WARN", (
        f"surfaces: {len(surfaces)} watched symlinked surface(s) not followed ({names}{suffix})"
        " — contents stay outside the inventory and the health score; see docs/heat-model.md"
    )


def coverage_health():
    result = scan_markdown(ROOT, watch_regex(), ignore_globs=scope_ignore())
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


def _clients_seen(events):
    """Summarize which clients have ever written, so a silent one is nameable.

    A project can look healthy on another client's telemetry while the one you
    are running has never recorded anything (issue #21). Naming both makes that
    visible in a single run instead of requiring a history read.
    """
    newest = {}
    for event in events:
        client = event.get("client")
        if isinstance(client, str) and client:
            # A client that wrote without a usable timestamp is still recorded;
            # dropping it would hide the very silence this line exists to show.
            stamp = event.get("ts") if isinstance(event.get("ts"), str) else ""
            newest[client] = max(newest.get(client, ""), stamp)
    if not newest:
        return ""
    listed = ", ".join(
        f"{client} {newest[client][:10] or 'unknown date'}" for client in sorted(newest)
    )
    return f" (recorded clients: {listed})"


def liveness_health():
    events = _lifecycle_events()
    current = session_id()
    if current:
        if any(event.get("t") == "session" and event.get("session") == current for event in events):
            return "PASS", "hook liveness: current session start was recorded"
        return (
            "FAIL",
            f"hook liveness: current session start is absent{_clients_seen(events)} — check /hooks, restart the session, then reinstall the plugin if still absent",
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
            f"hook liveness: events exist but are stale ({age_days} days){_clients_seen(events)} — informational; start a fresh session to verify",
        )
    # Codex exports no session id, so this lenient branch is all a Codex user
    # ever reaches. Naming the clients keeps another client's telemetry from
    # reading as your own hooks working, which is the issue #21 failure mirrored.
    return "PASS", f"hook liveness: recent session/read activity found{_clients_seen(events)}"


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
    for name in ("TT_WATCH_REGEX", "TT_SCAN_REGEX", "TT_ALWAYS_LOADED_REGEX", "TT_EDIT_REGEX"):
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
    topics = assignments.get("TT_LOG_TOPICS")
    if topics is not None and topics not in ("on", "off"):
        return "FAIL", "config: TT_LOG_TOPICS must be on or off"
    agents = assignments.get("TT_LOG_AGENTS")
    if agents is not None and agents not in ("on", "off"):
        return "FAIL", "config: TT_LOG_AGENTS must be on or off"
    commands = assignments.get("TT_LOG_COMMANDS")
    if commands is not None and commands not in ("off", "classified", "full"):
        return "FAIL", "config: TT_LOG_COMMANDS must be off, classified, or full"
    rotate = assignments.get("TT_ROTATE_BYTES")
    if rotate is not None:
        try:
            if int(rotate) <= 0:
                raise ValueError
        except ValueError:
            return "FAIL", "config: TT_ROTATE_BYTES must be a positive integer"
    return "PASS", "config: project override parses and validates"


def prompts_health():
    """Report the effective prompt privacy mode and which layer selected it (issue #13)."""
    mode, source = "hash", "built-in fallback"
    for label, path in (
        ("plugin default", os.path.join(PLUGIN_ROOT, "scripts", "tt-config.sh")),
        ("user default", user_config_path()),
        ("project override", os.path.join(ROOT, ".trigger-tree", "config.sh")),
    ):
        try:
            text = open(path, encoding="utf-8").read()
        except OSError:
            continue
        match = re.search(r"(?m)^TT_LOG_PROMPTS='([^']+)'", text)
        if match:
            mode, source = match.group(1), label
    if mode not in ("hash", "truncate", "off"):
        return "FAIL", (
            f"prompt logging: invalid mode '{mode}' from the {source} — use hash, truncate, or off"
        )
    if mode == "truncate":
        return "PASS", f"prompt logging: {mode} (set by the {source}); task previews available"
    return "WARN", (
        f"prompt logging: {mode} (set by the {source}); task-cluster previews unavailable — "
        "run /tt setup truncate to enable future local previews"
    )


def _effective_config(name, fallback):
    value, source = fallback, "built-in fallback"
    for label, path in (
        ("plugin default", os.path.join(PLUGIN_ROOT, "scripts", "tt-config.sh")),
        ("user default", user_config_path()),
        ("project override", os.path.join(ROOT, ".trigger-tree", "config.sh")),
    ):
        try:
            text = open(path, encoding="utf-8").read()
        except OSError:
            continue
        match = re.search(rf"(?m)^{re.escape(name)}='([^']*)'", text)
        if match:
            value, source = match.group(1), label
    return value, source


def instructions_health():
    if not os.path.isfile(MANIFEST_PATH) or os.path.islink(MANIFEST_PATH):
        return (
            "WARN",
            "instructions: no manifest — run `tt instructions --init`, then review and confirm probes",
        )
    try:
        manifest = tt_adherence.load_manifest(MANIFEST_PATH)
    except tt_adherence.ManifestError as error:
        return "FAIL", f"instructions: invalid manifest ({error}) — run `tt instructions --init`"
    drift = tt_adherence.manifest_drift(manifest, ROOT)
    if drift:
        paths = ", ".join(item["path"] for item in drift[:3])
        return (
            "WARN",
            f"instructions: manifest stale ({paths}) — run `tt instructions --init`; rates withheld",
        )

    # A probe that cannot fire looks identical to a rule nobody needed, so this
    # outranks capture warnings: it is broken authoring, not a missing setting.
    broken = [
        item
        for item in tt_adherence.selftest(manifest, ROOT)["probes"]
        if item["status"] in ("unreachable", "unsatisfiable")
    ]
    if broken:
        names = ", ".join(sorted(item["id"] for item in broken)[:3])
        return (
            "FAIL",
            f"instructions: {len(broken)} probe(s) can never fire ({names}) — "
            "run `tt instructions --selftest`; their silence measures nothing",
        )

    topics, _ = _effective_config("TT_LOG_TOPICS", "off")
    commands, _ = _effective_config("TT_LOG_COMMANDS", "off")
    edit_regex, _ = _effective_config("TT_EDIT_REGEX", r"(?!)")
    capture = {
        "topics": topics == "on",
        "commands": commands in ("classified", "full"),
        "edits": edit_regex != r"(?!)",
        "tests": True,
        "commits": True,
    }
    disabled = []
    for directive in manifest["directives"]:
        probe_type = directive["probe"]["type"]
        if probe_type != "unobservable" and not tt_adherence._capture_enabled(probe_type, capture):
            disabled.append(probe_type)
    if disabled:
        names = ", ".join(sorted(set(disabled)))
        return (
            "WARN",
            f"instructions: manifest current; capture disabled for {names} probes — "
            "run /tt setup; excluded from rates",
        )
    return "PASS", "instructions: manifest current and configured probes are observable"


def python_health():
    current = sys.version_info[:2]
    if SUPPORTED_PYTHON[0] <= current <= SUPPORTED_PYTHON[1]:
        return "PASS", (
            f"python: {current[0]}.{current[1]} is supported (3.10–3.14) — {sys.executable}"
        )
    return "FAIL", (
        f"python: {current[0]}.{current[1]} unsupported ({sys.executable}) — "
        "configure Python 3.10–3.14"
    )


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
        check
        for check in (
            hooks_health(),
            liveness_health(),
            codex_trust_health(),
            config_health(),
            agents_health(),
            prompts_health(),
            instructions_health(),
            coverage_health(),
            surfaces_health(),
            python_health(),
            ignore_health(),
            statusline_health(),
            history_health(),
        )
        if check is not None
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
