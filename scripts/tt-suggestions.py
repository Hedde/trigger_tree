#!/usr/bin/env python3
"""Print concise, deterministic router suggestions; keep full stats off stdout."""

import json
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def router_for(path):
    folder = path.rsplit("/", 1)[0] if "/" in path else "docs"
    return "docs/README.md" if folder == "docs" else f"{folder}/index.md"


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
        elif not item.get("referenced_from") and not item.get("template", False):
            add(
                ("gap", item["path"]),
                f"Review candidate: add a link to {item['path']} in {router_for(item['path'])} — no reads and no doc references it. {item['caveat']}",
            )

    # Backward-compatible fallback for pre-1.0 stats payloads.
    for item in stats.get("untouched_detail", []) if not stats.get("review_candidates") else []:
        if not item.get("referenced_from") and not item.get("template", False):
            path = item["path"]
            add(
                ("gap", path),
                f"Review candidate: add a link to {path} in {router_for(path)} — unread and no doc references it (router gap). Low reads can mean rare-but-critical; verify before archiving.",
            )

    for folder in stats.get("folders", []):
        name = folder["folder"]
        if name.startswith(".claude/") or name == "(root)":
            continue
        if not folder.get("has_index") and folder.get("coverage", 0) < 0.5:
            add(
                ("folder", name),
                f"Add {name}/index.md — {folder['touched']}/{folder['files']} files read and the folder has no entry point.",
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

    for hunt in stats.get("hunting", []):
        add(
            ("hunt", hunt["path"]),
            f"Sharpen the index instructions for {hunt['path']} — {hunt['scans']} searches indicate hunting instead of routed reads.",
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
