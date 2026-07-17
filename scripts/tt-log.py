#!/usr/bin/env python3
"""trigger-tree logger — invoked by the plugin hooks. Stdlib only, no jq needed.

Events (first argument):
  session  SessionStart hook
  prompt   UserPromptSubmit hook (respects TT_LOG_PROMPTS: truncate|hash|off)
  read     PostToolUse on Read|Glob|Grep (Read → "read", Glob/Grep → "scan")
  skill    PostToolUse on Skill (logs the skill name)
  note     manual annotation: tt-log.py note "text" (e.g. "sharpened UX router")

Appends one JSON line per event to $PROJECT/.trigger-tree/history.jsonl and rotates
the file to history-<utc-timestamp>.jsonl when it exceeds TT_ROTATE_BYTES.
Hooks must never disturb the session: every failure exits 0 silently.
"""
import hashlib
import json
import os
import re
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


def main():
    event = sys.argv[1] if len(sys.argv) > 1 else ""
    cfg = conf()
    rotate = int(cfg["TT_ROTATE_BYTES"])
    ts = now_ts()

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
