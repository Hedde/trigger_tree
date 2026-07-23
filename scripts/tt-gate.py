#!/usr/bin/env python3
"""CI gate for static documentation discoverability. Deterministic, telemetry-free.

Scores repository structure only — router listings, inbound links, folder entry
points, watch scope — so the result is identical on every machine and in CI.
Discoverable never means discovered: read telemetry stays local and is not used.

Exit codes: 0 pass, 1 gate failed, 2 usage or execution error.
"""

import argparse
import json
import os
import re
import stat
import subprocess
import sys
import tempfile

from tt_scope import parse_ignore, scan_markdown

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ.get("TT_PROJECT_DIR") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
BASELINE_PATH = os.path.join(".trigger-tree", "gate.json")
SCHEMA = 1
WEIGHTS = {"routed": 40, "linked": 30, "entry_points": 20, "watch_scope": 10}
SHOWN_OFFENDERS = 5
OFFENDER_KINDS = (
    (
        "unlisted",
        "TTD001",
        "warning",
        "Unlisted in their folder router",
        "add a link in the folder's entry point",
    ),
    (
        "orphans",
        "TTD002",
        "warning",
        "Orphans (no doc links to them)",
        "link from a router or related doc",
    ),
    (
        "folders_without_entry_point",
        "TTD003",
        "warning",
        "Folders without an entry point",
        "add README.md, _index.md, or index.md",
    ),
    (
        "unwatched",
        "TTD004",
        "note",
        "Outside the watch scope",
        "watch it via TT_WATCH_REGEX if agents should read it; leaving human-only "
        "files (templates, changelogs) unwatched is a valid choice",
    ),
)


def _fraction(numerator, denominator):
    return 1.0 if denominator == 0 else numerator / denominator


def structure_stats():
    """Run tt-stats without telemetry so the payload is a pure function of the repo."""
    result = subprocess.run(
        [sys.executable, os.path.join(SCRIPT_DIR, "tt-stats.py"), "--no-telemetry"],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def _conf_value(key):
    for path in (
        os.path.join(ROOT, ".trigger-tree", "config.sh"),
        os.path.join(SCRIPT_DIR, "tt-config.sh"),
    ):
        try:
            text = open(path, encoding="utf-8").read()
        except OSError:
            continue
        match = re.search(r"(?m)^" + key + r"='([^']*)'", text)
        if match:
            return match.group(1)
    return ""


def scope_ignore():
    return parse_ignore(_conf_value("TT_SCOPE_IGNORE"))


def watch_regex():
    for path in (
        os.path.join(ROOT, ".trigger-tree", "config.sh"),
        os.path.join(SCRIPT_DIR, "tt-config.sh"),
    ):
        try:
            text = open(path, encoding="utf-8").read()
        except OSError:
            continue
        match = re.search(r"(?m)^TT_WATCH_REGEX='([^']+)'", text)
        if match:
            return match.group(1)
    return r"(?!)"


def measure(stats):
    """Return components, offender lists, and the weighted 0-100 score."""
    coverage = stats.get("router_coverage", [])
    listed = sum(item.get("listed", 0) for item in coverage)
    members = sum(item.get("files", 0) for item in coverage)
    unlisted = sorted(
        path
        for item in coverage
        for path in item.get("unlisted", [])
        if not path.rsplit("/", 1)[-1].startswith("_")
    )

    detail = stats.get("untouched_detail", [])
    evaluable = [item for item in detail if not item.get("template", False)]
    orphans = sorted(
        item["path"]
        for item in evaluable
        if not item.get("inbound_refs")
        and not item.get("is_router")
        and not item.get("router_mentions_target")
    )

    skill_only = {
        item["path"].rsplit("/", 1)[0] for item in detail if item["path"].endswith("/SKILL.md")
    }
    doc_folders = {
        item["path"].rsplit("/", 1)[0] for item in detail if not item["path"].endswith("/SKILL.md")
    }
    folders = [
        folder
        for folder in stats.get("folders", [])
        if folder["folder"] != "(root)"
        and not folder["folder"].startswith(".claude/")
        and folder.get("files")
        # A folder whose members are all SKILL.md files is a skill package, not a
        # docs folder — requiring an index there would punish every plugin repo.
        and not (folder["folder"] in skill_only and folder["folder"] not in doc_folders)
    ]
    without_entry = sorted(f["folder"] for f in folders if not f.get("has_index"))

    pattern = re.compile(watch_regex())
    ignore_globs = scope_ignore()
    scope = scan_markdown(ROOT, pattern.pattern, ignore_globs=ignore_globs)
    unwatched = sorted(path for path in scope["paths"] if not pattern.search(path))
    components = {
        "routed": _fraction(listed, members),
        "linked": _fraction(len(evaluable) - len(orphans), len(evaluable)),
        "entry_points": _fraction(len(folders) - len(without_entry), len(folders)),
        "watch_scope": _fraction(scope["watched"], scope["markdown"]),
    }
    score = round(sum(WEIGHTS[name] * value for name, value in components.items()))
    return {
        "score": score,
        "components": {name: round(value * 100) for name, value in components.items()},
        "orphans": orphans,
        "unlisted": unlisted,
        "folders_without_entry_point": without_entry,
        "unwatched": unwatched,
        "scan_capped": bool(scope.get("capped")),
        "evaluable_docs": len(evaluable),
    }


def badge_payload(score):
    color = (
        "brightgreen"
        if score >= 90
        else (
            "green"
            if score >= 80
            else "yellow" if score >= 70 else "orange" if score >= 60 else "red"
        )
    )
    return {
        "schemaVersion": 1,
        "label": "docs discoverability",
        "message": f"{score}%",
        "color": color,
    }


def _refuse_unsafe(path):
    if os.path.lexists(path):
        mode = os.lstat(path).st_mode
        if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
            raise RuntimeError(f"refusing non-regular or symlinked destination: {path}")


def write_json(path, payload):
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    _refuse_unsafe(path)
    fd, temporary = tempfile.mkstemp(prefix=".gate.", dir=directory, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def load_baseline(path):
    try:
        data = json.loads(open(path, encoding="utf-8").read())
    except OSError:
        return None
    except ValueError:
        raise RuntimeError(f"baseline {path} is not valid JSON") from None
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        raise RuntimeError(f"baseline {path} has an unsupported schema")
    return data


def _offenders(label, paths, fix):
    lines = []
    if paths:
        lines.append(f"{label} ({len(paths)}):")
        for path in paths[:SHOWN_OFFENDERS]:
            lines.append(f"  - {path} — {fix}")
        if len(paths) > SHOWN_OFFENDERS:
            lines.append(f"  … +{len(paths) - SHOWN_OFFENDERS} more")
    return lines


def _version():
    manifest = os.path.join(os.path.dirname(SCRIPT_DIR), ".claude-plugin", "plugin.json")
    try:
        return json.loads(open(manifest, encoding="utf-8").read())["version"]
    except (OSError, ValueError, KeyError):
        return "unknown"


def sarif_payload(result, score, verdict):
    """SARIF 2.1.0: the standard exchange format for static-analysis findings."""
    rules, findings = [], []
    for key, rule_id, level, label, fix in OFFENDER_KINDS:
        rules.append(
            {
                "id": rule_id,
                "name": key.replace("_", "-"),
                "shortDescription": {"text": label},
                "help": {"text": fix},
            }
        )
        for path in result[key]:
            findings.append(
                {
                    "ruleId": rule_id,
                    "level": level,
                    "message": {"text": f"{label}: {path} — {fix}"},
                    "locations": [{"physicalLocation": {"artifactLocation": {"uri": path}}}],
                }
            )
    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "trigger-tree-gate",
                        "informationUri": "https://github.com/Hedde/trigger_tree",
                        "version": _version(),
                        "rules": rules,
                    }
                },
                "results": findings,
                "properties": {
                    "score": score,
                    "components": result["components"],
                    "verdict": verdict,
                },
            }
        ],
    }


def _write_step_summary(result, score, status_lines):
    """Mirror the verdict onto the GitHub run page when CI provides the hook."""
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    lines = [f"### 🌳 docs discoverability: {score}%", "", "| component | score |", "|---|---|"]
    for name, value in sorted(result["components"].items()):
        lines.append(f"| {name.replace('_', ' ')} | {value}% |")
    lines.append("")
    for key, _rule, _level, label, fix in OFFENDER_KINDS:
        paths = result[key]
        if not paths:
            continue
        lines.append(f"**{label} ({len(paths)})**")
        for offender in paths[:SHOWN_OFFENDERS]:
            lines.append(f"- `{offender}` — {fix}")
        if len(paths) > SHOWN_OFFENDERS:
            lines.append(f"- … +{len(paths) - SHOWN_OFFENDERS} more")
        lines.append("")
    lines.extend(f"**{line}**" for line in status_lines)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def run(argv=None):
    parser = argparse.ArgumentParser(prog="tt gate", description=__doc__)
    parser.add_argument("--min-score", type=int, default=None)
    parser.add_argument("--baseline", default=BASELINE_PATH)
    parser.add_argument("--update-baseline", action="store_true")
    parser.add_argument("--badge", default=None, metavar="PATH")
    parser.add_argument("--sarif", default=None, metavar="PATH")
    args = parser.parse_args(argv)

    result = measure(structure_stats())
    score = result["score"]
    parts = " · ".join(
        f"{name.replace('_', ' ')} {value}%" for name, value in sorted(result["components"].items())
    )
    print(f"🌳 docs discoverability: {score}% ({parts})")
    if not result["evaluable_docs"]:
        print("No watched documentation found — nothing to gate (see TT_WATCH_REGEX).")
    if result["scan_capped"]:
        print("note: the markdown scan hit its file cap — the watch-scope ratio is incomplete.")

    for key, _rule, _level, label, fix in OFFENDER_KINDS:
        for line in _offenders(label, result[key], fix):
            print(line)

    if args.badge:
        write_json(args.badge, badge_payload(score))
        print(f"badge written: {args.badge}")

    baseline_path = (
        os.path.join(ROOT, args.baseline) if not os.path.isabs(args.baseline) else args.baseline
    )
    if args.update_baseline:
        write_json(baseline_path, {"schema": SCHEMA, "score": score})
        print(f"baseline updated: {args.baseline} (score {score})")
        if args.sarif:
            write_json(args.sarif, sarif_payload(result, score, "baseline-updated"))
        _write_step_summary(result, score, [f"✅ baseline updated to {score}"])
        return 0

    failures = []
    if args.min_score is not None and score < args.min_score:
        failures.append(f"score {score} is below --min-score {args.min_score}")
    baseline = load_baseline(baseline_path)
    if baseline is not None and score < baseline["score"]:
        failures.append(
            f"score {score} regressed below the committed baseline {baseline['score']} "
            f"({args.baseline}) — fix the findings above or deliberately re-baseline "
            f"with --update-baseline"
        )
    if failures:
        for failure in failures:
            print(f"GATE FAILED: {failure}")
        if args.sarif:
            write_json(args.sarif, sarif_payload(result, score, "failed"))
        _write_step_summary(result, score, [f"❌ GATE FAILED: {failure}" for failure in failures])
        return 1
    if baseline is None and args.min_score is None:
        print(
            "No baseline committed yet — run `tt gate --update-baseline` and commit "
            f"{args.baseline} to enforce no-regression on every PR."
        )
    print("gate passed")
    if args.sarif:
        write_json(args.sarif, sarif_payload(result, score, "passed"))
    _write_step_summary(result, score, ["✅ gate passed"])
    return 0


def main():
    try:
        return run()
    except RuntimeError as error:
        print(f"tt gate: {error}", file=sys.stderr)
        return 2
    except subprocess.CalledProcessError as error:
        print(f"tt gate: analysis failed: {error.stderr.strip()[:200]}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
