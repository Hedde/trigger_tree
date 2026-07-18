#!/usr/bin/env python3
"""trigger-tree aggregator.

Combines $PROJECT/.trigger-tree/history*.jsonl (current file + rotated archives) with
an inventory of the documentation tree and prints a stats JSON to stdout.
Deterministic: all counting happens here so /tt only interprets, never computes.

Maturity model: files with zero reads are "untouched". They remain review signals,
never removal verdicts: cold-start → too early to judge; warming → early signal;
mature → enough history to review purpose, protection, and routing.

Config: $PROJECT/.trigger-tree/config.sh overrides the plugin default tt-config.sh.
Usage: python3 tt-stats.py [path/to/history.jsonl]
"""

import glob
import hashlib
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from fnmatch import fnmatch
from itertools import combinations

ROOT = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

MATURITY_MIN_READS = 30  # below this (or MIN_SESSIONS): cold-start
MATURITY_MIN_SESSIONS = 3
MATURE_MIN_READS = 100  # below this (or MATURE_MIN_DAYS): warming
MATURE_MIN_DAYS = 7
TREND_DAILY_MAX_DAYS = 14  # daily buckets up to here, weekly beyond
CLUSTER_JACCARD = 0.6  # min similarity to join an existing task cluster
HIGH_IN_LINK_COUNT = 3
SCHEMA_VERSION = 1


def _conf_texts():
    # Layered: project override → plugin default. Broken entries never crash.
    texts = []
    for path in (
        os.path.join(ROOT, ".trigger-tree", "config.sh"),
        os.path.join(SCRIPT_DIR, "tt-config.sh"),
    ):
        try:
            texts.append(open(path, encoding="utf-8").read())
        except OSError:
            continue
    return texts


def _conf_regex(name, fallback):
    for text in _conf_texts():
        m = re.search(name + r"='([^']+)'", text)
        if m:
            try:
                return re.compile(m.group(1))
            except re.error:
                continue
    return re.compile(fallback)


def _conf_value(name, fallback=""):
    for text in _conf_texts():
        match = re.search(name + r"='([^']*)'", text)
        if match:
            return match.group(1)
    return fallback


WATCH = _conf_regex("TT_WATCH_REGEX", r"^docs/.*\.md$")
ALWAYS = _conf_regex("TT_ALWAYS_LOADED_REGEX", r"^(CLAUDE|AGENTS)\.md$")
CRITICAL_GLOBS = [
    value.strip() for value in _conf_value("TT_CRITICAL_GLOB").split(",") if value.strip()
]
EXPERIMENTAL_OUTCOMES = _conf_value("TT_EXPERIMENTAL_OUTCOMES", "off") == "on"

INVENTORY_BASES = [
    "docs",
    "agents",
    "skills",
    "agent-briefs",
    ".claude/rules",
    ".claude/skills",
    ".",
]


def inventory():
    seen = set()
    for base in INVENTORY_BASES:
        top = os.path.join(ROOT, base)
        if not os.path.isdir(top):
            continue
        walker = os.walk(top) if base != "." else [(top, [], os.listdir(top))]
        for dirpath, _, files in walker:
            for f in files:
                rel = os.path.relpath(os.path.join(dirpath, f), ROOT).replace(os.sep, "/")
                if WATCH.search(rel):
                    seen.add(rel)
    return sorted(seen)


def history_files(explicit=None):
    if explicit:
        return [explicit]
    # Archives sort before history.jsonl ("-" < "."), oldest first: chronological order.
    return sorted(glob.glob(os.path.join(ROOT, ".trigger-tree", "history*.jsonl")))


def load_events_with_diagnostics(paths):
    events = []
    seen_tool_calls = set()
    diagnostics = {"legacy_migrated": 0, "future_rejected": 0, "corrupt_lines": 0}
    for path in paths:
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    diagnostics["corrupt_lines"] += 1
                    continue  # a torn write should not kill the whole report
                if not isinstance(event, dict):
                    diagnostics["corrupt_lines"] += 1
                    continue
                version = event.get("schema_version", 0)
                if version == 0:
                    event = {**event, "schema_version": SCHEMA_VERSION, "migrated_from": 0}
                    diagnostics["legacy_migrated"] += 1
                elif version != SCHEMA_VERSION:
                    diagnostics["future_rejected"] += 1
                    continue
                # Session resume/compaction can replay hook delivery around a boundary.
                # Claude's tool_use_id is stable for that call, so count it once even
                # when the duplicate straddles a rotated archive.
                tool_use_id = event.get("tool_use_id")
                if tool_use_id and event.get("t") in ("read", "scan", "skill"):
                    identity = (event.get("session"), event.get("t"), tool_use_id)
                    if identity in seen_tool_calls:
                        continue
                    seen_tool_calls.add(identity)
                events.append(event)
    return events, diagnostics


def load_events(paths):
    return load_events_with_diagnostics(paths)[0]


IMPORT_RE = re.compile(r"(?<![\w`])@([^\s`]+)")


def claude_import_graph(docs):
    """Return inventory files whose content is injected through CLAUDE.md imports.

    Imports are resolved relative to the importing file, remain inside the project,
    and are followed recursively with cycle protection. External/absolute imports
    are intentionally ignored because they cannot be classified in this inventory.
    """
    doc_set = set(docs)
    seeds = [p for p in docs if p == "CLAUDE.md" or p.endswith("/CLAUDE.md")]
    loaded = set(seeds)
    pending = list(seeds)
    while pending:
        source = pending.pop()
        try:
            text = open(os.path.join(ROOT, source), encoding="utf-8", errors="ignore").read()
        except OSError:
            continue
        base = posix_dirname(source)
        for raw in IMPORT_RE.findall(text):
            target = raw.rstrip(".,;:)").replace("\\", "/")
            if target.startswith(("/", "~", "http://", "https://")):
                continue
            candidate = os.path.normpath(os.path.join(base, target)).replace(os.sep, "/")
            if candidate.startswith("../") or candidate not in doc_set or candidate in loaded:
                continue
            loaded.add(candidate)
            pending.append(candidate)
    return loaded


def posix_dirname(path):
    return path.rsplit("/", 1)[0] if "/" in path else ""


def is_safety_path(path):
    return path.startswith(".claude/rules/") or path.startswith("security/") or "/security/" in path


def is_critical_tagged(text):
    return bool(
        re.search(r"(?im)^\s*(?:critical\s*:\s*true|trigger-tree\s*:\s*critical)\s*$", text)
    )


def protection_reasons(path, referenced_from, text, always_loaded):
    reasons = []
    if always_loaded:
        reasons.append("always loaded into context")
    if len(referenced_from) >= HIGH_IN_LINK_COUNT:
        reasons.append(f"referenced by {len(referenced_from)} other docs")
    if is_safety_path(path):
        reasons.append("safety path")
    matching_globs = [pattern for pattern in CRITICAL_GLOBS if fnmatch(path, pattern)]
    if matching_globs:
        reasons.append("critical glob " + ", ".join(matching_globs))
    if is_critical_tagged(text):
        reasons.append("tagged critical")
    return reasons


def fingerprint(paths):
    return hashlib.sha1("\n".join(sorted(paths)).encode()).hexdigest()[:10]


def parse_ts(ts):
    try:
        return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ")
    except (TypeError, ValueError):
        return None


def observed_days(timestamps):
    first, last = parse_ts(timestamps[0]), parse_ts(timestamps[-1])
    if not first or not last:
        return 0.0
    return round((last - first).total_seconds() / 86400, 2)


def grade_for(score):
    return (
        "A"
        if score >= 90
        else "B" if score >= 75 else "C" if score >= 60 else "D" if score >= 45 else "F"
    )


def jaccard(a, b):
    a, b = set(a), set(b)
    return len(a & b) / len(a | b) if a | b else 0.0


def main():
    explicit = sys.argv[1] if len(sys.argv) > 1 else None
    events, history_diagnostics = load_events_with_diagnostics(history_files(explicit))
    docs = inventory()

    reads = [e for e in events if e.get("t") == "read"]
    scans = [e for e in events if e.get("t") == "scan"]
    skill_events = [e for e in events if e.get("t") == "skill"]
    outcome_events = [e for e in events if e.get("t") == "outcome"]
    notes = [{"ts": e.get("ts"), "text": e.get("text", "")} for e in events if e.get("t") == "note"]
    sessions = sorted({e.get("session", "?") for e in events})

    per_file = defaultdict(
        lambda: {"reads": 0, "last_read": None, "sessions": set(), "agents": Counter()}
    )
    for e in reads:
        f = per_file[e["path"]]
        f["reads"] += 1
        f["last_read"] = max(filter(None, [f["last_read"], e.get("ts")]), default=None)
        f["sessions"].add(e.get("session", "?"))
        f["agents"][e.get("agent", "main")] += 1

    scan_targets = Counter(e["path"] for e in scans)

    per_skill = defaultdict(lambda: {"uses": 0, "sessions": set(), "last_used": None})
    for e in skill_events:
        s = per_skill[e["skill"]]
        s["uses"] += 1
        s["sessions"].add(e.get("session", "?"))
        s["last_used"] = max(filter(None, [s["last_used"], e.get("ts")]), default=None)

    # Fingerprints: the set of doc paths (and skills used) between two prompt markers.
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
        elif e.get("t") == "skill":
            current.setdefault(s, {"prompt": "(session start)", "paths": set()})
            current[s]["paths"].add(f"skill:{e['skill']}")
    buckets.extend(b for b in current.values() if b["paths"])

    fp_groups = defaultdict(lambda: {"count": 0, "prompts": [], "paths": []})
    for b in buckets:
        fp = fingerprint(b["paths"])
        g = fp_groups[fp]
        g["count"] += 1
        g["paths"] = sorted(b["paths"])
        if b["prompt"] and len(g["prompts"]) < 3:
            g["prompts"].append(b["prompt"][:120])

    # Task clusters: greedy Jaccard grouping of fingerprints — near-identical doc sets
    # (e.g. UX-ish tasks with one file of variance) land in the same cluster.
    clusters = []
    for g in sorted(fp_groups.values(), key=lambda g: -g["count"]):
        for c in clusters:
            if jaccard(g["paths"], c["paths"]) >= CLUSTER_JACCARD:
                c["count"] += g["count"]
                c["variants"] += 1
                c["prompts"] = (c["prompts"] + g["prompts"])[:3]
                break
        else:
            clusters.append(
                {
                    "paths": g["paths"],
                    "count": g["count"],
                    "variants": 1,
                    "prompts": list(g["prompts"]),
                }
            )
    clusters.sort(key=lambda c: -c["count"])

    co_read = Counter()
    for b in buckets:
        for a, c in combinations(sorted(b["paths"]), 2):
            co_read[(a, c)] += 1

    read_paths = set(per_file)
    timestamps = sorted(filter(None, (e.get("ts") for e in events)))
    days = observed_days(timestamps) if len(timestamps) >= 2 else 0.0

    if len(reads) < MATURITY_MIN_READS or len(sessions) < MATURITY_MIN_SESSIONS:
        maturity = "cold-start"
    elif len(reads) < MATURE_MIN_READS or days < MATURE_MIN_DAYS:
        maturity = "warming"
    else:
        maturity = "mature"

    # Trend: daily buckets for short periods, ISO-week buckets beyond. The hunting
    # ratio per bucket shows whether router changes (see `notes`) actually help.
    daily = days <= TREND_DAILY_MAX_DAYS
    trend_buckets = defaultdict(lambda: {"reads": 0, "scans": 0})
    for e in reads + scans:
        dt = parse_ts(e.get("ts"))
        if not dt:
            continue
        if daily:
            key = dt.strftime("%Y-%m-%d")
        else:
            iso = dt.isocalendar()
            key = f"{iso[0]}-W{iso[1]:02d}"
        trend_buckets[key][e["t"] + "s"] += 1
    trend = [
        {
            "period": k,
            **v,
            "hunting_ratio": round(v["scans"] / v["reads"], 2) if v["reads"] else None,
        }
        for k, v in sorted(trend_buckets.items())
    ]

    # Always-loaded files (system-prompt injection / Skill tool) can never be "dead":
    # their usage is invisible to Read-tool telemetry by design. A SKILL.md whose skill
    # was actually invoked counts as touched via the Skill-tool events.
    used_skill_files = {
        f".claude/skills/{name}/SKILL.md"
        for name in per_skill
        if f".claude/skills/{name}/SKILL.md" in set(docs)
    }
    imported_files = claude_import_graph(docs)
    always_loaded_set = {p for p in docs if ALWAYS.search(p)} | imported_files
    unread = [p for p in docs if p not in read_paths and p not in used_skill_files]
    untouched = [p for p in unread if p not in always_loaded_set]
    always_loaded = [p for p in unread if p in always_loaded_set]

    # Router-gap detection: an untouched file that no other doc links to is invisible
    # to the router; an untouched file that IS referenced points at content/naming.
    texts = {}
    for p in docs:
        try:
            texts[p] = open(os.path.join(ROOT, p), encoding="utf-8", errors="ignore").read()
        except OSError:
            texts[p] = ""
    untouched_detail = []
    for p in untouched:
        base = p.rsplit("/", 1)[-1]
        refs = [q for q, t in texts.items() if q != p and (p in t or base in t)]
        untouched_detail.append(
            {"path": p, "referenced_from": sorted(refs)[:5], "template": base.startswith("_")}
        )

    review_candidates = []
    for detail in untouched_detail:
        p = detail["path"]
        all_refs = [
            q for q, text in texts.items() if q != p and (p in text or p.rsplit("/", 1)[-1] in text)
        ]
        reasons = protection_reasons(p, all_refs, texts.get(p, ""), False)
        if detail["template"]:
            reasons.append("template or intentional archive")
        protected = bool(reasons)
        why = (
            reasons
            if protected
            else ["no reads in the measurement period", "not protected by critical-context rules"]
        )
        review_candidates.append(
            {
                **detail,
                "classification": "protected" if protected else "review_candidate",
                "why": why,
                "recommendation": (
                    "review, likely keep — rare-but-critical"
                    if protected
                    else "review context and routing"
                ),
                "caveat": "Low reads can mean rare-but-critical; verify purpose and owners before archiving.",
            }
        )

    protected_docs = []
    for p in always_loaded:
        protected_docs.append(
            {
                "path": p,
                "classification": "protected",
                "why": protection_reasons(p, [], texts.get(p, ""), True),
                "recommendation": "keep — always loaded",
            }
        )

    experimental_outcomes = None
    if EXPERIMENTAL_OUTCOMES:
        latest_outcome = {event.get("session", "?"): event for event in outcome_events}
        buckets_by_outcome = {
            "committed": {"sessions": set(), "reads": Counter()},
            "abandoned": {"sessions": set(), "reads": Counter()},
        }
        for event in reads:
            session = event.get("session", "?")
            outcome = latest_outcome.get(session)
            if not outcome:
                continue
            bucket = "committed" if outcome.get("git_commit_landed") else "abandoned"
            buckets_by_outcome[bucket]["sessions"].add(session)
            buckets_by_outcome[bucket]["reads"][event["path"]] += 1
        experimental_outcomes = {"label": "experimental correlation — not causal"}
        experimental_outcomes.update(
            {
                key: {
                    "sessions": len(value["sessions"]),
                    "docs": [
                        {"path": path, "reads": count}
                        for path, count in value["reads"].most_common(10)
                    ],
                }
                for key, value in buckets_by_outcome.items()
            }
        )

    # Folder heat/cold map: coverage (files touched) and read volume per folder.
    folder_map = defaultdict(lambda: {"files": 0, "touched": 0, "reads": 0})
    touched_paths = read_paths | used_skill_files
    for p in docs:
        folder = p.rsplit("/", 1)[0] if "/" in p else "(root)"
        fm = folder_map[folder]
        fm["files"] += 1
        if p in touched_paths:
            fm["touched"] += 1
        fm["reads"] += per_file[p]["reads"] if p in per_file else 0
    index_names = {"index.md", "_index.md", "README.md", "CLAUDE.md"}
    folders_with_index = {
        p.rsplit("/", 1)[0] if "/" in p else "(root)"
        for p in docs
        if p.rsplit("/", 1)[-1] in index_names
    }
    folders = [
        {
            "folder": k,
            **v,
            "coverage": round(v["touched"] / v["files"], 2),
            "has_index": k in folders_with_index,
        }
        for k, v in sorted(folder_map.items())
    ]

    # Documentation health: one deterministic grade a product owner can track.
    router_gaps = sum(1 for d in untouched_detail if not d["referenced_from"])
    denom = max(1, len(docs) - len(always_loaded))
    coverage_overall = round(len(touched_paths & set(docs)) / denom, 2)
    hunting_ratio = round(len(scans) / len(reads), 2) if reads else 0.0
    score = max(
        0,
        min(
            100,
            round(
                100
                - (1 - coverage_overall) * 40
                - min(20, router_gaps * 4)
                - min(20, hunting_ratio * 50)
            ),
        ),
    )
    health = {
        "score": score,
        "grade": grade_for(score),
        "coverage": coverage_overall,
        "drivers": [
            f"{len(untouched)} of {len(docs)} docs untouched",
            f"{router_gaps} router gaps (untouched and unreferenced)",
            f"hunting ratio {hunting_ratio}",
        ],
    }

    out = {
        "observed_from": timestamps[0] if timestamps else None,
        "observed_to": timestamps[-1] if timestamps else None,
        "observed_days": days,
        "sessions": len(sessions),
        "maturity": maturity,
        "health": health,
        "totals": {
            "events": len(events),
            "reads": len(reads),
            "scans": len(scans),
            "skill_uses": len(skill_events),
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
        "skills": [
            {
                "name": n,
                "uses": d["uses"],
                "sessions": len(d["sessions"]),
                "last_used": d["last_used"],
            }
            for n, d in sorted(per_skill.items(), key=lambda kv: -kv[1]["uses"])
        ],
        "untouched": untouched,
        "untouched_detail": untouched_detail,
        "review_candidates": review_candidates,
        "protected_docs": protected_docs,
        "folders": folders,
        "always_loaded": always_loaded,
        "always_loaded_imports": sorted(imported_files),
        "signal_integrity": {
            "subagent_reads": "captured",
            "subagent_read_events": sum(1 for e in reads if e.get("agent_id")),
            "compaction_boundaries": sum(
                1 for e in events if e.get("t") == "session" and e.get("source") == "compact"
            ),
        },
        "history_schema": {"current": SCHEMA_VERSION, **history_diagnostics},
        "experimental_outcomes": experimental_outcomes,
        "unknown_reads": sorted(p for p in read_paths if p not in docs),
        "hunting": [{"path": p, "scans": n} for p, n in scan_targets.most_common(10)],
        "trend": trend,
        "notes": notes,
        "clusters": clusters[:12],
        "co_read_top": [{"pair": list(pair), "count": n} for pair, n in co_read.most_common(15)],
    }
    json.dump(out, sys.stdout, indent=1)
    print()


if __name__ == "__main__":
    main()
