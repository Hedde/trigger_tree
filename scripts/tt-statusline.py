#!/usr/bin/env python3
"""trigger-tree statusline — live doc-discovery stats for the current session.

Portable (macOS/Linux), stdlib only. The dot pulses with the age of the last read or scan:
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
FRESH = "\033[1;38;5;114m"  # bright green
WARM = "\033[38;5;178m"  # amber
COLD = "\033[38;5;245m"  # dim

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

    files, scans, last, last_time = {}, 0, None, None
    with open(HIST, encoding="utf-8") as fh:
        for line in fh:
            if f'"session":"{session}"' not in line and f'"session": "{session}"' not in line:
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            typ = e.get("t")
            if typ == "read":
                files[e["path"]] = True
            elif typ == "scan":
                scans += 1
            else:
                continue
            try:
                event_time = datetime.strptime(e["ts"], "%Y-%m-%dT%H:%M:%SZ").replace(
                    tzinfo=timezone.utc
                )
            except (KeyError, ValueError):
                event_time = None
            if last is None or (
                event_time is not None and (last_time is None or event_time >= last_time)
            ):
                last, last_time = e, event_time

    if not files and not scans:
        print("🌳 tt: 0 docs consulted")
        return

    dirs = {os.path.dirname(p) for p in files}
    depth = max((p.count("/") for p in files), default=0)
    stats = f"{len(files)} files · {scans} scans · {len(dirs)} folders · depth {depth}"

    age = 10**9
    if last_time is not None:
        age = time.time() - last_time.timestamp()

    if age < 90:
        dot, color = "●", FRESH
    elif age < 600:
        dot, color = "◐", WARM
    else:
        dot, color = "○", COLD

    path = last["path"] + ("/" if last.get("t") == "scan" else "")
    print(f"🌳 {stats} {color}{dot} {path}{RESET}")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("🌳 tt")
    sys.exit(0)
