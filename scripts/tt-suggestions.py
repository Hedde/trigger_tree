#!/usr/bin/env python3
"""Print concise, deterministic router suggestions; keep full stats off stdout."""

import json
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def router_for(path, router_coverage=None):
    """Return a router proven to exist in stats; never invent index.md."""
    folder = path.rsplit("/", 1)[0] if "/" in path else "(root)"
    for item in router_coverage or []:
        if item.get("folder") == folder:
            return item.get("router")
    return None


def build_suggestions(stats):
    suggestions = []
    seen = set()

    def add(key, text):
        if key not in seen and len(suggestions) < 5:
            seen.add(key)
            suggestions.append(text)

    for item in stats.get("review_candidates", []):
        if item.get("classification") == "protected":
            add(
                ("protected", item["path"]),
                f"Review, likely keep — rare-but-critical: {item['path']} — {'; '.join(item['why'])}. {item['caveat']}",
            )
        elif (
            not item.get("template", False)
            and item.get("router")
            and not item.get("router_mentions_target", False)
        ):
            add(
                ("gap", item["path"]),
                f"Review candidate: add a link to {item['path']} in {item['router']} — both files exist and that router does not mention the target. {item['caveat']}",
            )

    # Pre-1.0 payloads lack enough repository evidence for a safe link edit.
    for item in stats.get("untouched_detail", []) if not stats.get("review_candidates") else []:
        if not item.get("referenced_from") and not item.get("template", False):
            path = item["path"]
            add(
                ("gap", path),
                f"Review routing for {path} — legacy telemetry shows no reads or references, but cannot verify an existing router target. Low reads can mean rare-but-critical; verify before editing.",
            )

    for coverage in stats.get("router_coverage", []):
        router = coverage.get("router")
        for path in coverage.get("unlisted", []):
            add(
                ("unlisted", path),
                f"Review candidate: add a link to {path} in {router} — both files exist and the folder router does not mention the target.",
            )

    for folder in stats.get("folders", []):
        name = folder["folder"]
        if name.startswith(".claude/") or name == "(root)":
            continue
        if not folder.get("has_index") and folder.get("coverage", 0) < 0.5:
            add(
                ("folder", name),
                f"Add a folder entry point in {name}/ (README.md, _index.md, or index.md) — {folder['touched']}/{folder['files']} files read and no existing router was found.",
            )

    for folder in stats.get("folders", []):
        name = folder["folder"]
        if (
            folder.get("coverage") == 0
            and name != "(root)"
            and not name.startswith(".claude/")
            and ("folder", name) not in seen
        ):
            add(
                ("cold", name),
                f"Review routing for {name}/ — none of its {folder['files']} files were read. Low reads can mean rare-but-critical; verify before archiving.",
            )

    for hunt in stats.get("search_activity", stats.get("hunting", [])):
        if hunt.get("pattern") == "distributed":
            add(
                ("hunt", hunt["path"]),
                f"Review routing for {hunt['path']} — {hunt['scans']} searches recur across {hunt['sessions']}/{hunt['total_sessions']} sessions ({hunt['tools']}); search telemetry is correlational, not proof of failed routing.",
            )

    for path in stats.get("unknown_reads", []):
        add(
            ("unknown", path),
            f"Fix the router reference to {path} — telemetry saw a read for a missing or renamed file.",
        )
    return suggestions


def main():
    result = subprocess.run(
        [sys.executable, os.path.join(SCRIPT_DIR, "tt-stats.py")],
        capture_output=True,
        text=True,
        check=True,
    )
    stats = json.loads(result.stdout)
    totals = stats["totals"]
    if stats["maturity"] == "cold-start":
        print(
            f"🌳 Not enough data yet ({totals['reads']} reads, {stats['sessions']} sessions) — suggestions need a few working sessions first."
        )
        return
    print(
        f"🌳 Suggestions — based on {totals['reads']} reads, {totals['scans']} searches, {stats['sessions']} sessions; proposes router edits only and changes nothing until you confirm."
    )
    suggestions = build_suggestions(stats)
    if not suggestions:
        print("No evidence-backed router changes found yet.")
        return
    for number, suggestion in enumerate(suggestions, 1):
        print(f"{number}. {suggestion}")
    print("Apply any of these? Reply with the numbers.")


if __name__ == "__main__":
    main()
