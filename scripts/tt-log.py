#!/usr/bin/env python3
"""trigger-tree logger — invoked by the plugin hooks. Stdlib only, no jq needed.

Events (first argument):
  session  SessionStart hook
  prompt   UserPromptSubmit hook (respects TT_LOG_PROMPTS: truncate|hash|off)
  read     PostToolUse on Read|Glob|Grep (Read → "read", Glob/Grep → "scan")
  bash     PostToolUse on Bash (explicit rg/grep/find doc targets → "scan")
  skill    PostToolUse on Skill (logs the skill name)
  note     manual annotation: tt-log.py note "text" (e.g. "sharpened UX router")
  ingest   external adapter entry point: tt-log.py ingest '{"t":"read","path":"docs/x.md"}'
           — lets any tool (a Codex wrapper, a git hook) append telemetry through a
           stable interface. Missing ts/session are stamped; unknown/invalid events
           are dropped silently.

Appends one JSON line per event to $PROJECT/.trigger-tree/history.jsonl and rotates
the file to history-<utc-timestamp>.jsonl when it exceeds TT_ROTATE_BYTES.
Hooks must never disturb the session: every failure exits 0 silently.
"""
import hashlib
import json
import os
import posixpath
import re
import shlex
import sys
import time

ROOT = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

DEFAULTS = {
    "TT_WATCH_REGEX": r"^docs/.*\.md$",
    "TT_SCAN_REGEX": r"^docs(/|$)",
    "TT_LOG_PROMPTS": "truncate",
    "TT_ROTATE_BYTES": "5242880",
}


def conf():
    # Layered per key: plugin default first, project override wins where present.
    out = dict(DEFAULTS)
    for path in (os.path.join(SCRIPT_DIR, "tt-config.sh"),
                 os.path.join(ROOT, ".trigger-tree", "config.sh")):
        try:
            text = open(path, encoding="utf-8").read()
        except OSError:
            continue
        for key in DEFAULTS:
            m = re.search(key + r"='([^']+)'", text)
            if m:
                out[key] = m.group(1)
    return out


def now_ts():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def append(obj, rotate_bytes):
    hist_dir = os.path.join(ROOT, ".trigger-tree")
    os.makedirs(hist_dir, exist_ok=True)
    hist = os.path.join(hist_dir, "history.jsonl")
    try:
        if os.path.getsize(hist) > rotate_bytes:
            stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
            os.rename(hist, os.path.join(hist_dir, f"history-{stamp}.jsonl"))
    except OSError:
        pass
    with open(hist, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(obj, ensure_ascii=False) + "\n")


def rel_path(target):
    # Normalize to forward slashes so logged paths are identical on all platforms.
    t = target.replace("\\", "/")
    root = ROOT.replace("\\", "/").rstrip("/") + "/"
    return t[len(root):] if t.startswith(root) else t


def shell_segments(command):
    """Tokenize a shell command without executing it, split at control operators."""
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars="|;&")
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:
        return []
    segments, current = [], []
    for token in tokens:
        if token and all(ch in "|;&" for ch in token):
            if current:
                segments.append(current)
                current = []
        else:
            current.append(token)
    if current:
        segments.append(current)
    return segments


def bash_scan_paths(command, scan_regex):
    """Return doc targets of explicit rg/grep/find commands, never their contents.

    Only existing path arguments are considered. This deliberately avoids guessing
    that arbitrary Bash commands or search patterns are documentation lookups.
    Multiple file arguments collapse to their common directory so one shell search
    produces one scan event rather than inflating the hunting count.
    """
    found = []
    for segment in shell_segments(command):
        tool_i = None
        for i, token in enumerate(segment):
            if os.path.basename(token).lower() in ("rg", "grep", "find"):
                tool_i = i
                break
        if tool_i is None:
            continue
        targets = []
        for token in segment[tool_i + 1:]:
            candidate = token if os.path.isabs(token) else os.path.join(ROOT, token)
            if os.path.exists(candidate):
                rel = rel_path(os.path.abspath(candidate)).rstrip("/") or "."
                if re.search(scan_regex, rel):
                    targets.append(rel if os.path.isdir(candidate) else posixpath.dirname(rel))
        targets = [target for target in targets if target]
        if targets:
            common = posixpath.commonpath(targets)
            if common not in found and re.search(scan_regex, common):
                found.append(common)
    return found


def main():
    event = sys.argv[1] if len(sys.argv) > 1 else ""
    cfg = conf()
    rotate = int(cfg["TT_ROTATE_BYTES"])
    ts = now_ts()

    if event == "ingest":
        try:
            obj = json.loads(sys.argv[2])
        except (IndexError, json.JSONDecodeError):
            return
        if obj.get("t") not in ("read", "scan", "skill", "note", "prompt", "session"):
            return
        if obj["t"] in ("read", "scan"):
            if not obj.get("path"):
                return
            obj["path"] = rel_path(str(obj["path"]))
        obj.setdefault("ts", ts)
        obj.setdefault("session", os.environ.get("CLAUDE_SESSION_ID", "external"))
        obj.setdefault("agent", "external")
        append(obj, rotate)
        return

    if event == "note":
        text = " ".join(sys.argv[2:]).strip()[:300]
        if text:
            session = os.environ.get("CLAUDE_SESSION_ID", "?")
            append({"t": "note", "ts": ts, "session": session, "text": text}, rotate)
        return

    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        data = {}
    session = data.get("session_id", "?")
    agent = data.get("agent_type", "main")

    if event == "session":
        append({"t": "session", "ts": ts, "session": session}, rotate)

    elif event == "prompt":
        entry = {"t": "prompt", "ts": ts, "session": session}
        mode = cfg["TT_LOG_PROMPTS"]
        prompt = (data.get("prompt") or "").replace("\n", " ")
        if mode == "truncate":
            entry["prompt"] = prompt[:200]
        elif mode == "hash":
            entry["prompt_hash"] = hashlib.sha1(prompt.encode()).hexdigest()[:10]
        # mode "off": marker only — fingerprints still work, no prompt text stored
        append(entry, rotate)

    elif event == "read":
        tool = data.get("tool_name", "?")
        tool_input = data.get("tool_input") or {}
        if tool == "Read":
            target, typ, regex = tool_input.get("file_path"), "read", cfg["TT_WATCH_REGEX"]
        else:
            target, typ, regex = tool_input.get("path"), "scan", cfg["TT_SCAN_REGEX"]
        if not target:
            return
        rel = rel_path(target)
        if not re.search(regex, rel):
            return
        append({"t": typ, "ts": ts, "session": session, "tool": tool,
                "path": rel, "agent": agent}, rotate)

    elif event == "bash":
        command = (data.get("tool_input") or {}).get("command", "")
        for path in bash_scan_paths(command, cfg["TT_SCAN_REGEX"]):
            append({"t": "scan", "ts": ts, "session": session, "tool": "Bash",
                    "path": path, "agent": agent}, rotate)

    elif event == "skill":
        name = (data.get("tool_input") or {}).get("skill", "")
        if name:
            append({"t": "skill", "ts": ts, "session": session,
                    "skill": name, "agent": agent}, rotate)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass  # a logging failure must never break the session
    sys.exit(0)
