#!/usr/bin/env python3
"""Print concise, deterministic router suggestions; keep full stats off stdout."""

import json
import os
import subprocess
import sys
from collections import Counter

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MAX_EDITS = 5
MAX_OBSERVATIONS = 2


def router_for(path, router_coverage=None):
    """Return a router proven to exist in stats; never invent index.md."""
    folder = path.rsplit("/", 1)[0] if "/" in path else "(root)"
    for item in router_coverage or []:
        if item.get("folder") == folder:
            return item.get("router")
    return None


def _early(maturity):
    return " (early signal)" if maturity == "warming" else ""


def _tools_label(tools):
    if isinstance(tools, dict):
        return ", ".join(f"{name} ×{count}" for name, count in sorted(tools.items()))
    return str(tools)


def build_suggestions(stats):
    """Return tiered output: appliable edits, observations, and a protected summary.

    Numbered edits are repository-verified link/entry-point changes only; telemetry
    signals that need judgment stay unnumbered so the apply-prompt never points at
    a no-op.
    """
    maturity = stats.get("maturity", "mature")
    edits = []
    seen_paths = set()
    edit_folders = set()

    for item in stats.get("review_candidates", []):
        if (
            item.get("classification") == "review_candidate"
            and not item.get("template", False)
            and item.get("router")
            and not item.get("router_mentions_target", False)
            and item["path"] not in seen_paths
        ):
            seen_paths.add(item["path"])
            inbound = item.get("inbound_refs", len(item.get("referenced_from", [])))
            plural = "" if inbound == 1 else "s"
            edits.append(
                f"Add a link to {item['path']} in {item['router']} — both files exist, "
                f"that router does not mention the target, and {inbound} other doc{plural} "
                f"link to it. {item['caveat']}"
            )

    for coverage in stats.get("router_coverage", []):
        router = coverage.get("router")
        for path in coverage.get("unlisted", []):
            if path.rsplit("/", 1)[-1].startswith("_") or path in seen_paths:
                continue
            seen_paths.add(path)
            edits.append(
                f"Add a link to {path} in {router} — both files exist and the folder "
                f"router does not mention the target "
                f"({coverage.get('listed', 0)}/{coverage.get('files', 0)} members listed)."
            )

    for folder in stats.get("folders", []):
        name = folder["folder"]
        if name.startswith(".claude/") or name == "(root)" or not folder.get("files"):
            continue
        if not folder.get("has_index") and folder.get("coverage", 0) < 0.5:
            edit_folders.add(name)
            edits.append(
                f"Add a folder entry point in {name}/ (README.md, _index.md, or index.md) — "
                f"{folder['touched']}/{folder['files']} files read and no existing router "
                f"was found."
            )

    observations = []
    for hunt in stats.get("search_activity", stats.get("hunting", [])):
        if hunt.get("pattern") == "distributed":
            observations.append(
                f"Worth a look: {hunt['path']} — {hunt['scans']} searches recur across "
                f"{hunt['sessions']}/{hunt['total_sessions']} sessions "
                f"({_tools_label(hunt['tools'])}); search telemetry is correlational, "
                f"not proof of failed routing.{_early(maturity)}"
            )

    for folder in stats.get("folders", []):
        name = folder["folder"]
        if (
            folder.get("coverage") == 0
            and folder.get("files")
            and name != "(root)"
            and not name.startswith(".claude/")
            and name not in edit_folders
        ):
            observations.append(
                f"Worth a look: {name}/ — none of its {folder['files']} files were read. "
                f"Low reads can mean rare-but-critical; verify before "
                f"archiving.{_early(maturity)}"
            )

    # Pre-1.0 payloads lack enough repository evidence for a safe link edit.
    if not stats.get("review_candidates"):
        for item in stats.get("untouched_detail", []):
            if not item.get("referenced_from") and not item.get("template", False):
                observations.append(
                    f"Worth a look: {item['path']} — legacy telemetry shows no reads or "
                    f"references, but cannot verify an existing router target. Low reads "
                    f"can mean rare-but-critical; verify before editing."
                )

    for path in stats.get("unknown_reads", []):
        observations.append(
            f"Worth a look: {path} — the file exists and was read, but is outside the "
            f"current documentation inventory."
        )

    protected = [
        item
        for item in stats.get("review_candidates", [])
        if item.get("classification") == "protected"
    ]
    summary = None
    if protected:
        reasons = Counter(
            "heavily referenced" if reason.startswith("referenced by ") else reason
            for item in protected
            for reason in item.get("why", [])
        )
        top = [name for name, _ in sorted(reasons.items(), key=lambda kv: (-kv[1], kv[0]))[:2]]
        count = len(protected)
        noun = "file" if count == 1 else "files"
        verb = "looks" if count == 1 else "look"
        summary = (
            f"{count} low-read {noun} {verb} rare-but-critical ({'; '.join(top)}) — "
            f"likely fine; details in /tt insights."
        )

    return {
        "edits": edits[:MAX_EDITS],
        "extra_edits": max(0, len(edits) - MAX_EDITS),
        "observations": observations[:MAX_OBSERVATIONS],
        "protected_summary": summary,
    }


def main():
    show_apply_prompt = "--no-apply-prompt" not in sys.argv[1:]
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
    tiers = build_suggestions(stats)
    if tiers["edits"]:
        for number, suggestion in enumerate(tiers["edits"], 1):
            print(f"{number}. {suggestion}")
        if tiers["extra_edits"]:
            print(f"+{tiers['extra_edits']} more — see /tt insights")
    else:
        print("No evidence-backed router edits found.")
    for line in tiers["observations"]:
        print(line)
    if tiers["protected_summary"]:
        print(tiers["protected_summary"])
    if tiers["edits"] and show_apply_prompt:
        print("Apply any of these? Reply with the numbers.")


if __name__ == "__main__":
    main()
