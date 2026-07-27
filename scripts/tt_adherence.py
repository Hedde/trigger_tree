"""Deterministic instruction-adherence manifest validation and evaluation.

The model may help author a manifest, but every metric in this module is a pure,
stdlib-only computation over that manifest and the local event stream.
"""

import hashlib
import json
import os
import re
from collections import defaultdict
from datetime import datetime
from fnmatch import fnmatch

SCHEMA_VERSION = 1
MIN_CONFIDENT_OPPORTUNITIES = 5
MAX_EVIDENCE = 5
TOKEN_ESTIMATE_CHARS = 4
MAX_PATTERN_LENGTH = 512
PROBE_TYPES = (
    "command_after_edit",
    "command_before_commit",
    "path_avoided",
    "route_followed",
    "skill_used",
    "tests_before_commit",
    "unobservable",
)
COMMAND_PROBES = {"command_after_edit", "command_before_commit"}
# Why a directive cannot be machine-checked. The distinction matters: a rule with
# no objectively testable condition is unlikely to fire for the model either, so
# it is advice to the author. The rest are boundaries of this tool, not defects
# in the rule, and the two must not be reported as one number.
UNOBSERVABLE_REASONS = (
    "outside-capture",
    "requires-diff",
    "requires-judgment",
    "subjective-condition",
)
AUTHOR_ACTIONABLE_REASONS = {"subjective-condition"}
TOPIC_PROBES = {"route_followed", "skill_used"}
EDIT_PROBES = {"command_after_edit", "path_avoided"}


class ManifestError(ValueError):
    """A human-actionable manifest validation error."""


def _is_slug(value):
    return isinstance(value, str) and bool(re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", value))


def _string_list(value):
    return (
        isinstance(value, list)
        and bool(value)
        and all(isinstance(item, str) and bool(item) for item in value)
    )


def safe_command_pattern(pattern):
    """Accept the bounded regex subset safe enough for a five-second hook."""
    if not isinstance(pattern, str) or not pattern or len(pattern) > MAX_PATTERN_LENGTH:
        return False
    if re.search(r"\(\?|\\[1-9]|\{|[)][*+?]", pattern):
        return False
    wildcard_repeats = re.findall(r"(?<!\\)\.[*+]", pattern)
    if len(wildcard_repeats) > 1:
        return False
    stripped = re.sub(r"(?<!\\)\.[*+]", "", pattern)
    return not re.search(r"(?<!\\)[*+]", stripped)


def instruction_hash(path):
    """Return the SHA-256 of one instruction file without following symlinks."""
    if os.path.islink(path) or not os.path.isfile(path):
        raise ManifestError(f"instruction file is missing or unsafe: {path}")
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_manifest(manifest):
    """Validate and return a normalized, deterministically ordered manifest."""
    if not isinstance(manifest, dict):
        raise ManifestError("manifest must be a JSON object")
    if manifest.get("schema") != SCHEMA_VERSION:
        raise ManifestError(f"manifest schema must be {SCHEMA_VERSION}")
    files = manifest.get("instruction_files")
    if not isinstance(files, list) or not files:
        raise ManifestError("instruction_files must be a non-empty list")
    normalized_files = []
    seen_paths = set()
    for entry in files:
        if not isinstance(entry, dict) or set(entry) != {"path", "sha256"}:
            raise ManifestError("each instruction file needs only path and sha256")
        path = entry["path"]
        digest = entry["sha256"]
        if (
            not isinstance(path, str)
            or not path
            or os.path.isabs(path)
            or ".." in path.replace("\\", "/").split("/")
        ):
            raise ManifestError("instruction file paths must be project-relative")
        if path in seen_paths:
            raise ManifestError(f"duplicate instruction file: {path}")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ManifestError(f"invalid sha256 for {path}")
        seen_paths.add(path)
        normalized_files.append({"path": path.replace("\\", "/"), "sha256": digest})

    directives = manifest.get("directives")
    if not isinstance(directives, list):
        raise ManifestError("directives must be a list")
    normalized_directives = []
    seen_ids = set()
    seen_patterns = set()
    for directive in directives:
        if not isinstance(directive, dict):
            raise ManifestError("each directive must be an object")
        directive_id = directive.get("id")
        if not _is_slug(directive_id):
            raise ManifestError("directive ids must be lowercase slugs")
        if directive_id in seen_ids:
            raise ManifestError(f"duplicate directive id: {directive_id}")
        seen_ids.add(directive_id)
        source = directive.get("source")
        if (
            not isinstance(source, dict)
            or source.get("file") not in seen_paths
            or not isinstance(source.get("line"), int)
            or source["line"] < 1
            or (
                "end_line" in source
                and (not isinstance(source["end_line"], int) or source["end_line"] < source["line"])
            )
        ):
            raise ManifestError(f"{directive_id}: invalid source")
        if "text" in directive and not isinstance(directive["text"], str):
            raise ManifestError(f"{directive_id}: text must be a string")
        probe = directive.get("probe")
        if not isinstance(probe, dict) or probe.get("type") not in PROBE_TYPES:
            raise ManifestError(f"{directive_id}: unknown probe type")
        probe_type = probe["type"]
        required = {
            "route_followed": ("topics", "paths"),
            "command_before_commit": ("pattern_id", "pattern"),
            "command_after_edit": ("when_edited", "pattern_id", "pattern"),
            "skill_used": ("topics", "skills"),
            "tests_before_commit": (),
            "path_avoided": ("forbidden",),
            "unobservable": ("why",),
        }[probe_type]
        for key in required:
            value = probe.get(key)
            valid = (
                _is_slug(value)
                if key == "pattern_id"
                else (
                    isinstance(value, str) and bool(value)
                    if key in ("pattern", "when_edited", "forbidden", "why")
                    else _string_list(value)
                )
            )
            if not valid:
                raise ManifestError(f"{directive_id}: invalid or missing {key}")
        # Optional so existing manifests keep validating unchanged.
        if probe_type == "unobservable" and probe.get("reason") is not None:
            if probe["reason"] not in UNOBSERVABLE_REASONS:
                raise ManifestError(
                    f"{directive_id}: unobservable reason must be one of "
                    f"{', '.join(UNOBSERVABLE_REASONS)}"
                )
        if probe_type in COMMAND_PROBES:
            pattern_id = probe["pattern_id"]
            if pattern_id in seen_patterns:
                raise ManifestError(f"duplicate command pattern_id: {pattern_id}")
            seen_patterns.add(pattern_id)
            try:
                re.compile(probe["pattern"])
            except re.error as error:
                raise ManifestError(f"{directive_id}: invalid command pattern: {error}") from error
            if not safe_command_pattern(probe["pattern"]):
                raise ManifestError(
                    f"{directive_id}: command pattern exceeds the safe regex subset"
                )
        normalized_directives.append(
            {
                "id": directive_id,
                "source": dict(source),
                **({"text": directive["text"]} if "text" in directive else {}),
                "probe": dict(probe),
            }
        )
    return {
        "schema": SCHEMA_VERSION,
        "instruction_files": sorted(normalized_files, key=lambda item: item["path"]),
        "directives": sorted(normalized_directives, key=lambda item: item["id"]),
    }


def load_manifest(path):
    try:
        with open(path, encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, json.JSONDecodeError) as error:
        raise ManifestError(f"cannot read manifest: {error}") from error
    return validate_manifest(value)


def manifest_drift(manifest, root):
    """Return stable drift diagnostics for the manifest's instruction files."""
    drift = []
    for entry in manifest["instruction_files"]:
        path = os.path.join(root, *entry["path"].split("/"))
        try:
            actual = instruction_hash(path)
        except ManifestError:
            drift.append({"path": entry["path"], "status": "missing"})
            continue
        if actual != entry["sha256"]:
            drift.append({"path": entry["path"], "status": "changed"})
    return drift


def manifest_fingerprint(manifest):
    encoded = json.dumps(validate_manifest(manifest), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def probe_fingerprint(manifest):
    """Hash only what changes the meaning of an already-recorded event.

    Recorded events carry topic labels and command pattern ids. Those are
    interpretable exactly as long as the declared topic set and the
    pattern-id-to-pattern mapping are unchanged. Instruction prose, directive
    text, and source lines deliberately do not participate: editing a sentence
    in CLAUDE.md must never discard evidence gathered under identical probe
    semantics, because the before/after trend is the point of the measurement.
    """
    normalized = validate_manifest(manifest)
    topics = set()
    patterns = {}
    for directive in normalized["directives"]:
        probe = directive["probe"]
        topics.update(str(topic).lower() for topic in probe.get("topics", []))
        if probe["type"] in COMMAND_PROBES:
            patterns[probe["pattern_id"]] = probe["pattern"]
    encoded = json.dumps(
        {"topics": sorted(topics), "patterns": sorted(patterns.items())},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(encoded.encode()).hexdigest()


def _carries_probe_evidence(event):
    """True when an event's meaning depends on the probe semantics of its era."""
    return any(key in event for key in ("topics", "matched", "command"))


def _parse_ts(value):
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _week(value):
    parsed = _parse_ts(value)
    if not parsed:
        return None
    monday = parsed.date()
    monday = monday.fromordinal(monday.toordinal() - monday.weekday())
    return monday.isoformat()


def _event_before(left, right):
    return left["_index"] < right["_index"]


def _command_matches(event, probe):
    if event.get("t") not in ("command", "bash"):
        return False
    if probe["pattern_id"] in event.get("matched", []):
        return True
    command = event.get("command")
    return isinstance(command, str) and bool(re.search(probe["pattern"], command))


def _capture_enabled(probe_type, capture):
    if probe_type in TOPIC_PROBES:
        return capture.get("topics", False)
    if probe_type in EDIT_PROBES and not capture.get("edits", False):
        return False
    if probe_type in COMMAND_PROBES:
        return capture.get("commands", False) and (
            probe_type != "command_before_commit" or capture.get("commits", False)
        )
    if probe_type == "tests_before_commit":
        return capture.get("tests", True) and capture.get("commits", False)
    return True


def _probe_session(probe, events):
    probe_type = probe["type"]
    topics = {
        topic.lower()
        for event in events
        if event.get("t") == "prompt"
        for topic in event.get("topics", [])
        if isinstance(topic, str)
    }
    commits = [event for event in events if event.get("t") == "commit"]
    if probe_type == "route_followed":
        if not topics.intersection(topic.lower() for topic in probe["topics"]):
            return None
        followed = any(
            event.get("t") == "read" and event.get("path") in probe["paths"] for event in events
        )
        return "followed" if followed else "unobserved"
    if probe_type == "skill_used":
        if not topics.intersection(topic.lower() for topic in probe["topics"]):
            return None
        followed = any(
            event.get("t") == "skill" and event.get("skill") in probe["skills"] for event in events
        )
        return "followed" if followed else "unobserved"
    if probe_type == "command_before_commit":
        if not commits:
            return None
        followed = any(
            _command_matches(command, probe) and _event_before(command, commit)
            for commit in commits
            for command in events
        )
        return "followed" if followed else "unobserved"
    if probe_type == "tests_before_commit":
        if not commits:
            return None
        followed = any(
            test.get("t") == "test" and test.get("status") == "pass" and _event_before(test, commit)
            for commit in commits
            for test in events
        )
        return "followed" if followed else "unobserved"
    if probe_type == "command_after_edit":
        edits = [
            event
            for event in events
            if event.get("t") == "edit" and fnmatch(event.get("path", ""), probe["when_edited"])
        ]
        if not edits:
            return None
        followed = any(
            _command_matches(command, probe) and _event_before(edit, command)
            for edit in edits
            for command in events
        )
        return "followed" if followed else "unobserved"
    if probe_type == "path_avoided":
        finding = any(
            event.get("t") == "edit" and fnmatch(event.get("path", ""), probe["forbidden"])
            for event in events
        )
        return "unobserved" if finding else None
    raise AssertionError(f"no evaluator registered for {probe_type}")


GLOB_ALPHABET = "abcxyz0129_-."


def _glob_example(pattern):
    """Build one concrete path satisfying an fnmatch glob, or None if we cannot.

    Used only to prove a probe is reachable. Returning None is a reportable
    finding, never an assertion that the glob is wrong.
    """
    out = []
    index = 0
    while index < len(pattern):
        char = pattern[index]
        if char in "*?":
            out.append("x")
        elif char == "[":
            close = pattern.find("]", index + 1)
            if close == -1:
                return None
            body = pattern[index + 1 : close]
            negated = body[:1] in ("!", "^")
            if negated:
                body = body[1:]
                choice = next((item for item in GLOB_ALPHABET if item not in body), None)
            else:
                choice = body[:1] or None
            if choice is None:
                return None
            out.append(choice)
            index = close + 1
            continue
        else:
            out.append(char)
        index += 1
    candidate = "".join(out)
    return candidate if fnmatch(candidate, pattern) else None


def _probe_cases(probe):
    """Synthesize (expected result, events) pairs that must exercise a probe.

    These never touch the event log; they are constructed in memory so a probe
    can be proved reachable without waiting for a real opportunity to occur.
    """
    probe_type = probe["type"]
    if probe_type in TOPIC_PROBES:
        trigger = {"t": "prompt", "topics": [probe["topics"][0]]}
        satisfy = (
            {"t": "read", "path": probe["paths"][0]}
            if probe_type == "route_followed"
            else {"t": "skill", "skill": probe["skills"][0]}
        )
        return [("followed", [trigger, satisfy]), ("unobserved", [trigger])]
    if probe_type == "command_before_commit":
        command = {"t": "command", "matched": [probe["pattern_id"]]}
        return [("followed", [command, {"t": "commit"}]), ("unobserved", [{"t": "commit"}])]
    if probe_type == "tests_before_commit":
        test = {"t": "test", "status": "pass"}
        return [("followed", [test, {"t": "commit"}]), ("unobserved", [{"t": "commit"}])]
    if probe_type == "command_after_edit":
        path = _glob_example(probe["when_edited"])
        if path is None:
            return None
        edit = {"t": "edit", "path": path}
        command = {"t": "command", "matched": [probe["pattern_id"]]}
        return [("followed", [edit, command]), ("unobserved", [edit])]
    path = _glob_example(probe["forbidden"])
    return None if path is None else [("unobserved", [{"t": "edit", "path": path}])]


def selftest(manifest, root=None):
    """Prove every observable probe can fire, without running an agent.

    A probe that never fires against real history is ambiguous: the rule may
    never have applied, or the probe may be written so it can never match
    anything. This separates those two, deterministically and in memory.

    With `root`, a `route_followed` probe that points at a file which does not
    exist is reported as unsatisfiable: reads of it can never be recorded, so
    the directive would sit at zero forever while looking merely unlucky.

    It does not prove a command regex matches the commands you actually run;
    classified capture stores pattern ids, so only reachability is checked.
    """
    normalized = validate_manifest(manifest)
    results = []
    for directive in normalized["directives"]:
        probe = directive["probe"]
        entry = {"id": directive["id"], "source": directive["source"], "probe": probe["type"]}
        if probe["type"] == "unobservable":
            results.append({**entry, "status": "unobservable"})
            continue
        if root and probe["type"] == "route_followed":
            missing = [
                path
                for path in probe["paths"]
                if not os.path.isfile(os.path.join(root, *path.split("/")))
            ]
            if missing:
                results.append(
                    {
                        **entry,
                        "status": "unsatisfiable",
                        "reason": f"declared path does not exist: {missing[0]}",
                    }
                )
                continue
        cases = _probe_cases(probe)
        if cases is None:
            results.append(
                {
                    **entry,
                    "status": "unreachable",
                    "reason": "no example path satisfies the declared glob",
                }
            )
            continue
        failures = []
        for expected, events in cases:
            indexed = [
                {**event, "session": "selftest", "_index": index}
                for index, event in enumerate(events)
            ]
            actual = _probe_session(probe, indexed)
            if actual != expected:
                failures.append({"expected": expected, "actual": actual})
        if failures:
            results.append(
                {
                    **entry,
                    "status": "unreachable",
                    "reason": "constructed evidence did not produce the declared result",
                    "failures": failures,
                }
            )
        else:
            results.append({**entry, "status": "reachable"})
    return {
        "schema": SCHEMA_VERSION,
        "probes": results,
        "caveat": "reachability only; a command pattern is not tested against real commands",
        "summary": {
            "directives": len(results),
            "reachable": sum(item["status"] == "reachable" for item in results),
            "unreachable": sum(item["status"] == "unreachable" for item in results),
            "unsatisfiable": sum(item["status"] == "unsatisfiable" for item in results),
            "unobservable": sum(item["status"] == "unobservable" for item in results),
        },
    }


REQUIRED_CAPTURE = {
    "route_followed": ("topics",),
    "skill_used": ("topics",),
    "command_after_edit": ("edits", "commands"),
    "command_before_commit": ("commands", "instrumented"),
    "path_avoided": ("edits",),
    "tests_before_commit": ("instrumented",),
}


def _session_capture(session_events):
    """Which captures were demonstrably active during one recorded session.

    A directive cannot be called never-triggered over sessions in which the
    capture it depends on was not running: that is missing instrumentation,
    not a rule nobody needed. `instrumented` marks a session recorded by the
    adherence-aware hook, where commits are logged unconditionally, so their
    absence really does mean no commit happened.
    """
    return {
        "instrumented": any("probe_hash" in event for event in session_events),
        "topics": any(event.get("t") == "prompt" and "topics" in event for event in session_events),
        "edits": any(event.get("t") == "edit" for event in session_events),
        "commands": any(event.get("t") == "command" for event in session_events),
    }


def _measurable_sessions(probe_type, session_capture):
    required = REQUIRED_CAPTURE.get(probe_type, ())
    return sum(
        all(capture.get(key, False) for key in required) for capture in session_capture.values()
    )


def _session_groups(events):
    grouped = defaultdict(list)
    for index, raw in enumerate(events):
        if not isinstance(raw, dict):
            continue
        event = {**raw, "_index": index}
        grouped[str(event.get("session", "?"))].append(event)
    return {session: grouped[session] for session in sorted(grouped)}


def evaluate(events, manifest, now, capture=None, maturity="cold-start"):
    """Evaluate every directive once per session, deterministically.

    `now` is explicit to keep this pure. Capture-disabled probes are excluded,
    rather than turned into negative evidence.
    """
    del now  # reserved for future bounded-window evaluation; never read wall-clock time
    normalized = validate_manifest(manifest)
    expected_hash = manifest_fingerprint(normalized)
    expected_probes = probe_fingerprint(normalized)
    # Only evidence whose meaning depends on probe semantics is bound to them.
    # Raw observations (reads, edits, commits, tests) stay valid across edits.
    events = [
        event
        for event in events
        if not (
            isinstance(event, dict)
            and _carries_probe_evidence(event)
            and event.get("probe_hash") != expected_probes
        )
    ]
    capture = {
        "topics": False,
        "commands": False,
        "edits": False,
        "tests": True,
        "commits": False,
        **(capture or {}),
    }
    sessions = _session_groups(events)
    session_capture = {
        session: _session_capture(session_events) for session, session_events in sessions.items()
    }
    output = []
    unobservable = 0
    disabled = 0
    for directive in normalized["directives"]:
        probe = directive["probe"]
        probe_type = probe["type"]
        if probe_type == "unobservable":
            unobservable += 1
            output.append(
                {
                    "id": directive["id"],
                    "source": directive["source"],
                    "status": "unobservable",
                    "why": probe["why"],
                    **({"reason": probe["reason"]} if probe.get("reason") else {}),
                }
            )
            continue
        if not _capture_enabled(probe_type, capture):
            disabled += 1
            output.append(
                {
                    "id": directive["id"],
                    "source": directive["source"],
                    "status": "capture-disabled",
                    "opportunities": 0,
                    "followed": 0,
                    "unobserved": 0,
                    "rate": None,
                    "confidence": "unavailable",
                    "evidence": [],
                    "trend": [],
                }
            )
            continue
        observations = []
        degraded = []
        for session, session_events in sessions.items():
            result = _probe_session(probe, session_events)
            if result is None:
                continue
            timestamps = [event.get("ts") for event in session_events if _parse_ts(event.get("ts"))]
            ts = max(timestamps) if timestamps else None
            record = {"session": session, "ts": ts, "result": result}
            compacted = any(
                event.get("t") == "session" and event.get("source") == "compact"
                for event in session_events
            )
            if compacted and result == "unobserved":
                record["signal"] = "degraded-after-compaction"
                degraded.append(record)
            else:
                observations.append(record)
        opportunities = len(observations)
        followed = sum(item["result"] == "followed" for item in observations)
        unobserved = opportunities - followed
        measurable = _measurable_sessions(probe_type, session_capture)
        if observations or degraded:
            status = "measured"
        elif not measurable:
            # Nothing was watching yet; silence here is missing instrumentation.
            status = "awaiting-capture"
        elif probe_type == "path_avoided":
            # A forbidden edit is the finding, so no trigger means the rule held.
            status = "no-violations-observed"
        else:
            status = "never-triggered"
        rate = round(followed / opportunities, 2) if opportunities else None
        confidence = (
            "provisional" if opportunities < MIN_CONFIDENT_OPPORTUNITIES or degraded else maturity
        )
        trend_buckets = defaultdict(lambda: {"opportunities": 0, "followed": 0})
        for item in observations:
            period = _week(item["ts"])
            if period:
                trend_buckets[period]["opportunities"] += 1
                trend_buckets[period]["followed"] += item["result"] == "followed"
        trend = [
            {
                "period": period,
                "opportunities": bucket["opportunities"],
                "followed": bucket["followed"],
                "rate": round(bucket["followed"] / bucket["opportunities"], 2),
            }
            for period, bucket in sorted(trend_buckets.items())
        ]
        all_evidence = sorted(
            observations + degraded,
            key=lambda item: (item.get("ts") or "", item["session"], item["result"]),
        )
        output.append(
            {
                "id": directive["id"],
                "source": directive["source"],
                "status": status,
                "opportunities": opportunities,
                "followed": followed,
                "unobserved": unobserved,
                "degraded_opportunities": len(degraded),
                "measurable_sessions": measurable,
                "rate": rate,
                "confidence": confidence,
                "first_seen": all_evidence[0].get("ts") if all_evidence else None,
                "last_opportunity": all_evidence[-1].get("ts") if all_evidence else None,
                "evidence": all_evidence[-MAX_EVIDENCE:],
                "trend": trend,
            }
        )
    observable = len(normalized["directives"]) - unobservable
    return {
        "schema": SCHEMA_VERSION,
        "manifest_hash": expected_hash,
        "probe_hash": expected_probes,
        "sessions": len(sessions),
        "maturity": maturity,
        "confidence_threshold": MIN_CONFIDENT_OPPORTUNITIES,
        "uncertainty": "unobserved means evidence was not captured; it does not mean violated",
        "directives": output,
        "summary": {
            "directives": len(output),
            "observable": observable,
            "unobservable": unobservable,
            "unobservable_ratio": round(unobservable / len(output), 2) if output else 0.0,
            # Split so the author-actionable half is not hidden inside a boundary count.
            "no_testable_condition": sum(
                item.get("reason") in AUTHOR_ACTIONABLE_REASONS for item in output
            ),
            "unobservable_reasons": {
                reason: sum(item.get("reason") == reason for item in output)
                for reason in UNOBSERVABLE_REASONS
                if any(item.get("reason") == reason for item in output)
            },
            "capture_disabled": disabled,
            "never_triggered": sum(item.get("status") == "never-triggered" for item in output),
            "awaiting_capture": sum(item.get("status") == "awaiting-capture" for item in output),
            "no_violations_observed": sum(
                item.get("status") == "no-violations-observed" for item in output
            ),
            "measured": sum(item.get("status") == "measured" for item in output),
        },
    }


def estimate_cost(manifest, root, always_loaded=None, sessions=0, observed_days=0.0):
    """Estimate always-loaded and per-directive cost at four characters/token."""
    normalized = validate_manifest(manifest)
    paths = (
        sorted(set(always_loaded))
        if always_loaded is not None
        else [entry["path"] for entry in normalized["instruction_files"]]
    )
    files = {}
    total_bytes = 0
    for relative in paths:
        path = os.path.join(root, *relative.split("/"))
        try:
            if os.path.islink(path):
                continue
            with open(path, encoding="utf-8", errors="replace") as handle:
                text = handle.read()
        except OSError:
            continue
        files[relative] = text
        total_bytes += len(text.encode("utf-8"))
    per_directive = []
    for directive in normalized["directives"]:
        source = directive["source"]
        lines = files.get(source["file"], "").splitlines(keepends=True)
        start = source["line"] - 1
        end = source.get("end_line", source["line"])
        excerpt = "".join(lines[start:end])
        byte_count = len(excerpt.encode("utf-8"))
        per_directive.append(
            {
                "id": directive["id"],
                "bytes": byte_count,
                "estimated_tokens": round(len(excerpt) / TOKEN_ESTIMATE_CHARS),
            }
        )
    return {
        "always_loaded_bytes": total_bytes,
        "estimated_tokens_per_session": round(
            sum(len(text) for text in files.values()) / TOKEN_ESTIMATE_CHARS
        ),
        "estimation": f"estimated as Unicode characters / {TOKEN_ESTIMATE_CHARS}; no tokenizer",
        "sessions_observed": sessions,
        "days_observed": observed_days,
        "directives": per_directive,
    }
