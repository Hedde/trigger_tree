#!/usr/bin/env python3
"""trigger-tree statusline — live doc-discovery stats for the current session.

Portable (macOS/Linux), stdlib only. The dot pulses with the age of the last read:
● bright green < 90s, ◐ amber < 10min, ○ dim otherwise.
Register in project or user settings under "statusLine" with a refreshInterval.
"""
import json
import os
import sys
import time
from datetime import datetime, timezone

ROOT = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
HIST = os.path.join(ROOT, ".trigger-tree", "history.jsonl")

RESET = "\033[0m"
FRESH = "\033[1;38;5;114m"   # bright green
WARM = "\033[38;5;178m"      # amber
COLD = "\033[38;5;245m"      # dim

try:
    sys.stdout.reconfigure(encoding="utf-8")  # emoji-safe on Windows consoles
except AttributeError:  # pragma: no cover — exotic stdout replacement
    pass


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        data = {}
    session = data.get("session_id")
    if not session or not os.path.isfile(HIST):
        print("🌳 tt: no data")
        return

    files, last = {}, None
    with open(HIST, encoding="utf-8") as fh:
        for line in fh:
            if f'"session":"{session}"' not in line and f'"session": "{session}"' not in line:
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            if e.get("t") == "read":
                files[e["path"]] = True
                last = e

    if not files:
        print("🌳 tt: 0 docs consulted")
        return

    dirs = {os.path.dirname(p) for p in files}
    depth = max(p.count("/") for p in files)
    stats = f"{len(files)} files · {len(dirs)} folders · depth {depth}"

    age = 10**9
    try:
        then = datetime.strptime(last["ts"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        age = time.time() - then.timestamp()
    except (KeyError, ValueError):
        pass

    if age < 90:
        dot, color = "●", FRESH
    elif age < 600:
        dot, color = "◐", WARM
    else:
        dot, color = "○", COLD

    print(f"🌳 {stats} {color}{dot} {last['path']}{RESET}")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("🌳 tt")
    sys.exit(0)
