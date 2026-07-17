#!/usr/bin/env python3
"""Trigger Tree aggregator.

Combines $PROJECT/.trigger-tree/history.jsonl with an inventory of the documentation
tree and prints a stats JSON to stdout. Deterministic: all counting happens here so
/tt only interprets, never computes.

Maturity model: files with zero reads are "untouched". Whether untouched may be
interpreted as "dead" depends on the `maturity` field: cold-start → too early to
judge; warming → early signal; mature → untouched files are dead-path candidates.

Config: $PROJECT/.trigger-tree/config.sh overrides the plugin default tt-config.sh.
Usage: python3 tt-stats.py [path/to/history.jsonl]
"""
import hashlib
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from itertools import combinations

ROOT = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

MATURITY_MIN_READS = 30      # below this (or MIN_SESSIONS): cold-start
MATURITY_MIN_SESSIONS = 3
MATURE_MIN_READS = 100       # below this (or MATURE_MIN_DAYS): warming
MATURE_MIN_DAYS = 7


def _conf_text():
    proj = os.path.join(ROOT, ".trigger-tree", "config.sh")
    path = proj if os.path.isfile(proj) else os.path.join(SCRIPT_DIR, "tt-config.sh")
    return open(path).read()


def _conf_regex(text, name, fallback):
    m = re.search(name + r"='([^']+)'", text)
    return re.compile(m.group(1) if m else fallback)


_conf = _conf_text()
WATCH = _conf_regex(_conf, "TT_WATCH_REGEX", r"^docs/.*\.md$")
ALWAYS = _conf_regex(_conf, "TT_ALWAYS_LOADED_REGEX", r"^(CLAUDE|AGENTS)\.md$")

INVENTORY_BASES = ["docs", "agents", "skills", "agent-briefs", ".claude/rules", ".claude/skills", "."]


def inventory():
    seen = set()
    for base in INVENTORY_BASES:
        top = os.path.join(ROOT, base)
        if not os.path.isdir(top):
            continue
        walker = os.walk(top) if base != "." else [(top, [], os.listdir(top))]
        for dirpath, _, files in walker:
            for f in files:
                rel = os.path.relpath(os.path.join(dirpath, f), ROOT)
                if WATCH.search(rel):
                    seen.add(rel)
    return sorted(seen)


def load_events(hist_path):
    events = []
    if not os.path.isfile(hist_path):
        return events
    with open(hist_path) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue  # a torn write should not kill the whole report
    return events


def fingerprint(paths):
    return hashlib.sha1("\n".join(sorted(paths)).encode()).hexdigest()[:10]


def observed_days(timestamps):
    if len(timestamps) < 2:
        return 0.0
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    try:
        span = datetime.strptime(timestamps[-1], fmt) - datetime.strptime(timestamps[0], fmt)
        return round(span.total_seconds() / 86400, 2)
    except ValueError:
        return 0.0


def main():
    hist_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, ".trigger-tree", "history.jsonl")
    events = load_events(hist_path)
    docs = inventory()

    reads = [e for e in events if e.get("t") == "read"]
    scans = [e for e in events if e.get("t") == "scan"]
    sessions = sorted({e.get("session", "?") for e in events})

    per_file = defaultdict(lambda: {"reads": 0, "last_read": None, "sessions": set(), "agents": Counter()})
    for e in reads:
        f = per_file[e["path"]]
        f["reads"] += 1
        f["last_read"] = max(filter(None, [f["last_read"], e.get("ts")]), default=None)
        f["sessions"].add(e.get("session", "?"))
        f["agents"][e.get("agent", "main")] += 1

    scan_targets = Counter(e["path"] for e in scans)

    # Fingerprints: the set of doc paths read between two prompt markers (per session).
    buckets = []
    current = {}  # session -> {"prompt": str, "paths": set}
    for e in events:
        s = e.get("session", "?")
        if e.get("t") == "prompt":
            if s in current and current[s]["paths"]:
                buckets.append(current[s])
            current[s] = {"prompt": e.get("prompt", ""), "paths": set()}
        elif e.get("t") == "read":
            current.setdefault(s, {"prompt": "(session start)", "paths": set()})
            current[s]["paths"].add(e["path"])
    buckets.extend(b for b in current.values() if b["paths"])

    fp_groups = defaultdict(lambda: {"count": 0, "prompts": [], "paths": []})
    for b in buckets:
        fp = fingerprint(b["paths"])
        g = fp_groups[fp]
        g["count"] += 1
        g["paths"] = sorted(b["paths"])
        if b["prompt"] and len(g["prompts"]) < 3:
            g["prompts"].append(b["prompt"][:120])

    co_read = Counter()
    for b in buckets:
        for a, c in combinations(sorted(b["paths"]), 2):
            co_read[(a, c)] += 1

    read_paths = set(per_file)
    timestamps = sorted(filter(None, (e.get("ts") for e in events)))
    days = observed_days(timestamps)

    if len(reads) < MATURITY_MIN_READS or len(sessions) < MATURITY_MIN_SESSIONS:
        maturity = "cold-start"
    elif len(reads) < MATURE_MIN_READS or days < MATURE_MIN_DAYS:
        maturity = "warming"
    else:
        maturity = "mature"

    # Always-loaded files (system-prompt injection / Skill tool) can never be "dead":
    # their usage is invisible to Read-tool telemetry by design.
    unread = [p for p in docs if p not in read_paths]
    untouched = [p for p in unread if not ALWAYS.search(p)]
    always_loaded = [p for p in unread if ALWAYS.search(p)]

    out = {
        "observed_from": timestamps[0] if timestamps else None,
        "observed_to": timestamps[-1] if timestamps else None,
        "observed_days": days,
        "sessions": len(sessions),
        "maturity": maturity,
        "totals": {
            "events": len(events),
            "reads": len(reads),
            "scans": len(scans),
            "prompts_with_doc_reads": len(buckets),
            "inventory_files": len(docs),
        },
        "files": [
            {
                "path": p,
                "reads": d["reads"],
                "last_read": d["last_read"],
                "sessions": len(d["sessions"]),
                "agents": dict(d["agents"]),
            }
            for p, d in sorted(per_file.items(), key=lambda kv: -kv[1]["reads"])
        ],
        "untouched": untouched,
        "always_loaded": always_loaded,
        "unknown_reads": sorted(p for p in read_paths if p not in docs),
        "hunting": [{"path": p, "scans": n} for p, n in scan_targets.most_common(10)],
        "fingerprints": sorted(
            ({"fp": fp, **g} for fp, g in fp_groups.items()),
            key=lambda g: -g["count"],
        ),
        "co_read_top": [
            {"pair": list(pair), "count": n} for pair, n in co_read.most_common(15)
        ],
    }
    json.dump(out, sys.stdout, indent=1)
    print()


if __name__ == "__main__":
    main()
