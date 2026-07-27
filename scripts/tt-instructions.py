#!/usr/bin/env python3
"""Author and report deterministic instruction-adherence probes.

Exit codes: 0 success, 1 adherence threshold failed, 2 usage/manifest error.
"""

import argparse
import json
import os
import stat
import subprocess
import sys
import tempfile

import tt_adherence

ROOT = os.environ.get("TT_PROJECT_DIR") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MANIFEST_PATH = os.path.join(ROOT, ".trigger-tree", "directives.json")


def _regular_file(path):
    try:
        return stat.S_ISREG(os.lstat(path).st_mode)
    except OSError:
        return False


def _instruction_paths():
    return [
        name
        for name in ("CLAUDE.md", "AGENTS.md", "GEMINI.md")
        if _regular_file(os.path.join(ROOT, name))
    ]


def init_manifest():
    """Create a hash-bound scaffold, or refresh hashes without changing probes."""
    paths = _instruction_paths()
    if not paths:
        raise tt_adherence.ManifestError(
            "no root CLAUDE.md, AGENTS.md, or GEMINI.md instruction file found"
        )
    directives = []
    if _regular_file(MANIFEST_PATH):
        existing = tt_adherence.load_manifest(MANIFEST_PATH)
        directives = existing["directives"]
        paths = [item["path"] for item in existing["instruction_files"]]
    manifest = tt_adherence.validate_manifest(
        {
            "schema": tt_adherence.SCHEMA_VERSION,
            "instruction_files": [
                {
                    "path": path,
                    "sha256": tt_adherence.instruction_hash(os.path.join(ROOT, *path.split("/"))),
                }
                for path in paths
            ],
            "directives": directives,
        }
    )
    telemetry = os.path.dirname(MANIFEST_PATH)
    os.makedirs(telemetry, mode=0o700, exist_ok=True)
    if os.path.islink(telemetry):
        raise tt_adherence.ManifestError("refusing symlinked .trigger-tree directory")
    fd, temporary = tempfile.mkstemp(prefix=".directives-", suffix=".json", dir=telemetry)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2)
            handle.write("\n")
        os.chmod(temporary, 0o600)
        os.replace(temporary, MANIFEST_PATH)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
    return manifest


def stats_payload():
    process = subprocess.run(
        [sys.executable, os.path.join(SCRIPT_DIR, "tt-stats.py")],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "TT_PROJECT_DIR": ROOT},
    )
    if process.returncode:
        raise tt_adherence.ManifestError(process.stderr.strip() or "stats failed")
    try:
        return json.loads(process.stdout)
    except json.JSONDecodeError as error:
        raise tt_adherence.ManifestError("stats returned invalid JSON") from error


def _adherence():
    if not _regular_file(MANIFEST_PATH):
        return None
    return stats_payload().get("adherence")


def _print_report(adherence):
    if adherence["status"] == "stale":
        print("Instruction manifest is stale; run `tt instructions --init`.")
        return
    if adherence["status"] == "invalid":
        print(f"Instruction manifest is invalid: {adherence['error']}")
        return
    summary = adherence["summary"]
    print(
        f"Instruction adherence · {summary['observable']} observable · "
        f"{summary['unobservable']} unobservable · "
        f"{summary['capture_disabled']} capture-disabled"
    )
    print("Unobserved means evidence was not captured; it does not mean violated.")
    for item in adherence["directives"]:
        status = item["status"]
        if status == "measured":
            rate = f"{round(item['rate'] * 100)}%"
            detail = (
                f"{item['followed']}/{item['opportunities']} followed · "
                f"{rate} · {item['confidence']}"
            )
        elif status == "never-triggered":
            detail = (
                f"never-triggered in {item.get('measurable_sessions', 0)} measurable sessions "
                "(review prompt, not a removal recommendation)"
            )
        elif status == "awaiting-capture":
            detail = "awaiting-capture (no session yet recorded the signal this probe needs)"
        elif status == "no-violations-observed":
            detail = "no-violations-observed (the rule held wherever it could be checked)"
        elif status == "capture-disabled":
            detail = "capture-disabled (excluded from rates)"
        else:
            detail = f"unobservable · {item['why']}"
        print(f"- {item['id']}: {detail}")
    print(adherence["cost"]["headline"])


def _print_selftest(result):
    summary = result["summary"]
    print(
        f"Probe self-test · {summary['reachable']} reachable · "
        f"{summary['unreachable']} unreachable · "
        f"{summary['unsatisfiable']} unsatisfiable · {summary['unobservable']} unobservable"
    )
    print("Reachability only; a command pattern is not tested against real commands.")
    for item in result["probes"]:
        if item["status"] == "reachable":
            detail = f"reachable · {item['probe']}"
        elif item["status"] == "unobservable":
            detail = "unobservable · nothing to exercise"
        elif item["status"] == "unsatisfiable":
            detail = f"UNSATISFIABLE · {item['probe']} · {item['reason']}"
        else:
            detail = f"UNREACHABLE · {item['probe']} · {item['reason']}"
        print(f"- {item['id']}: {detail}")
    if summary["unreachable"] or summary["unsatisfiable"]:
        print("A probe that cannot fire measures nothing; its silence is not evidence.")


def _explain(adherence, directive_id):
    item = next(
        (entry for entry in adherence.get("directives", []) if entry["id"] == directive_id),
        None,
    )
    if item is None:
        raise tt_adherence.ManifestError(f"unknown directive: {directive_id}")
    return {
        "id": item["id"],
        "source": item["source"],
        "status": item["status"],
        "opportunities": item.get("opportunities"),
        "followed": item.get("followed"),
        "unobserved": item.get("unobserved"),
        "measurable_sessions": item.get("measurable_sessions"),
        "rate": item.get("rate"),
        "confidence": item.get("confidence"),
        "evidence": item.get("evidence", []),
        "uncertainty": adherence.get("uncertainty"),
    }


def _check(adherence, minimum, min_measured=0):
    if adherence.get("status") != "current":
        raise tt_adherence.ManifestError(
            "instruction manifest must be current before adherence can be checked"
        )
    failed = [
        item
        for item in adherence["directives"]
        if item.get("status") == "measured"
        and item.get("rate") is not None
        and item["rate"] < minimum
    ]
    summary = adherence.get("summary", {})
    measured = summary.get(
        "measured",
        sum(item.get("status") == "measured" for item in adherence["directives"]),
    )
    observable = summary.get("observable", 0)
    if failed:
        for item in failed:
            print(
                f"FAIL {item['id']}: {item['rate']:.2f} < {minimum:.2f} "
                "(unobserved does not mean violated)"
            )
        return 1
    # A gate that reports PASS without saying how much evidence it saw is the
    # same silent-degradation bug as a green tick on a privacy-limited mode.
    coverage = f"{measured}/{observable} observable directives measured"
    if measured < min_measured:
        print(f"FAIL instruction adherence: {coverage}, fewer than the required {min_measured}")
        return 1
    print(f"PASS instruction adherence: {coverage}, all measured rates >= {minimum:.2f}")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--init", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--explain", metavar="ID")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--min-rate", type=float, default=0.0)
    parser.add_argument("--min-measured", type=int, default=0)
    args = parser.parse_args(argv)
    if not 0 <= args.min_rate <= 1:
        parser.error("--min-rate must be between 0 and 1")
    if args.min_measured < 0:
        parser.error("--min-measured must not be negative")
    if args.init and (args.explain or args.check):
        parser.error("--init cannot be combined with --explain or --check")
    if args.selftest and (args.init or args.explain or args.check):
        parser.error("--selftest cannot be combined with --init, --explain, or --check")
    try:
        if args.init:
            manifest = init_manifest()
            if args.json:
                json.dump(manifest, sys.stdout, indent=2)
                print()
            else:
                print(
                    f"Initialized {os.path.relpath(MANIFEST_PATH, ROOT)}; "
                    "review and confirm probes before measurement."
                )
            return 0
        if args.selftest:
            if not _regular_file(MANIFEST_PATH):
                print("No instruction manifest; run `tt instructions --init`.")
                return 0
            # Deliberately manifest-only: no history, no config, no agent run.
            result = tt_adherence.selftest(tt_adherence.load_manifest(MANIFEST_PATH), ROOT)
            if args.json:
                json.dump(result, sys.stdout, indent=2)
                print()
            else:
                _print_selftest(result)
            broken = result["summary"]["unreachable"] + result["summary"]["unsatisfiable"]
            return 1 if broken else 0
        adherence = _adherence()
        if adherence is None:
            print("No instruction manifest; run `tt instructions --init`.")
            return 0
        if args.explain:
            explanation = _explain(adherence, args.explain)
            if args.json:
                json.dump(explanation, sys.stdout, indent=2)
                print()
            else:
                print(
                    f"{explanation['id']}: {explanation['status']} · "
                    f"{explanation['followed'] or 0}/{explanation['opportunities'] or 0} "
                    "followed"
                )
                print("Unobserved means evidence was not captured; it does not mean violated.")
                for evidence in explanation["evidence"]:
                    print(
                        f"- {evidence['session']} · {evidence.get('ts') or 'time unavailable'} "
                        f"· {evidence['result']}"
                    )
            return 0
        if args.check:
            return _check(adherence, args.min_rate, args.min_measured)
        if args.json:
            json.dump(adherence, sys.stdout, indent=2)
            print()
        else:
            _print_report(adherence)
        return 0
    except tt_adherence.ManifestError as error:
        print(f"tt instructions: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
