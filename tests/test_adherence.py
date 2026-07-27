import hashlib
import io
import json
import subprocess
import sys

import pytest
from conftest import load_script


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def manifest(text="rules\n", directives=None):
    return {
        "schema": 1,
        "instruction_files": [{"path": "CLAUDE.md", "sha256": digest(text)}],
        "directives": directives or [],
    }


def directive(directive_id, probe, line=1, end_line=None):
    source = {"file": "CLAUDE.md", "line": line}
    if end_line is not None:
        source["end_line"] = end_line
    return {"id": directive_id, "source": source, "text": directive_id, "probe": probe}


def test_manifest_validation_hash_drift_and_fingerprint(tmp_path):
    mod = load_script("tt_adherence.py", tmp_path)
    text = "rules\n"
    (tmp_path / "CLAUDE.md").write_bytes(text.encode())
    value = manifest(
        text,
        [
            directive(
                "run-tests",
                {
                    "type": "command_before_commit",
                    "pattern_id": "pytest",
                    "pattern": "pytest",
                },
            )
        ],
    )
    normalized = mod.validate_manifest(value)
    assert normalized["directives"][0]["id"] == "run-tests"
    assert mod.manifest_drift(normalized, tmp_path) == []
    assert mod.manifest_fingerprint(normalized) == mod.manifest_fingerprint(value)
    (tmp_path / "CLAUDE.md").write_text("changed\n")
    assert mod.manifest_drift(normalized, tmp_path) == [{"path": "CLAUDE.md", "status": "changed"}]
    (tmp_path / "CLAUDE.md").unlink()
    assert mod.manifest_drift(normalized, tmp_path) == [{"path": "CLAUDE.md", "status": "missing"}]


@pytest.mark.parametrize(
    "mutation,message",
    [
        (lambda value: [], "manifest must"),
        (lambda value: {**value, "schema": 2}, "schema"),
        (lambda value: {**value, "instruction_files": []}, "instruction_files"),
        (
            lambda value: {
                **value,
                "instruction_files": [{"path": "../CLAUDE.md", "sha256": "a" * 64}],
            },
            "project-relative",
        ),
        (
            lambda value: {
                **value,
                "directives": [directive("BAD", {"type": "unobservable", "why": "human judgment"})],
            },
            "lowercase slugs",
        ),
        (
            lambda value: {
                **value,
                "directives": [
                    directive("bad-probe", {"type": "command_before_commit", "pattern": "("})
                ],
            },
            "pattern_id",
        ),
    ],
)
def test_manifest_validation_errors(tmp_path, mutation, message):
    mod = load_script("tt_adherence.py", tmp_path)
    with pytest.raises(mod.ManifestError, match=message):
        mod.validate_manifest(mutation(manifest()))


def test_remaining_manifest_validation_boundaries(tmp_path):
    mod = load_script("tt_adherence.py", tmp_path)
    base = manifest()
    bad_values = [
        {**base, "instruction_files": ["CLAUDE.md"]},
        {
            **base,
            "instruction_files": [
                base["instruction_files"][0],
                base["instruction_files"][0],
            ],
        },
        {
            **base,
            "instruction_files": [{"path": "CLAUDE.md", "sha256": "not-a-hash"}],
        },
        {**base, "directives": "no"},
        {**base, "directives": ["no"]},
        {
            **base,
            "directives": [
                directive("same", {"type": "unobservable", "why": "x"}),
                directive("same", {"type": "unobservable", "why": "x"}),
            ],
        },
        {
            **base,
            "directives": [
                {**directive("bad-source", {"type": "unobservable", "why": "x"}), "source": {}}
            ],
        },
        {
            **base,
            "directives": [
                {
                    **directive("bad-text", {"type": "unobservable", "why": "x"}),
                    "text": 3,
                }
            ],
        },
        {
            **base,
            "directives": [
                directive("bad-type", {"type": "future-probe"}),
            ],
        },
        {
            **base,
            "directives": [
                directive(
                    "bad-regex",
                    {
                        "type": "command_before_commit",
                        "pattern_id": "check",
                        "pattern": "(",
                    },
                )
            ],
        },
        {
            **base,
            "directives": [
                directive(
                    "unsafe-regex",
                    {
                        "type": "command_before_commit",
                        "pattern_id": "unsafe",
                        "pattern": "(a+)+$",
                    },
                )
            ],
        },
        {
            **base,
            "directives": [
                directive(
                    "one",
                    {
                        "type": "command_before_commit",
                        "pattern_id": "check",
                        "pattern": "one",
                    },
                ),
                directive(
                    "two",
                    {
                        "type": "command_after_edit",
                        "when_edited": "*.py",
                        "pattern_id": "check",
                        "pattern": "two",
                    },
                ),
            ],
        },
    ]
    for value in bad_values:
        with pytest.raises(mod.ManifestError):
            mod.validate_manifest(value)
    missing = tmp_path / "missing.json"
    with pytest.raises(mod.ManifestError, match="cannot read manifest"):
        mod.load_manifest(missing)
    missing.write_text("{")
    with pytest.raises(mod.ManifestError, match="cannot read manifest"):
        mod.load_manifest(missing)
    with pytest.raises(mod.ManifestError, match="missing or unsafe"):
        mod.instruction_hash(missing.parent / "absent")
    assert mod._parse_ts("bad") is None
    assert mod._week(None) is None


def test_all_probe_types_are_deterministic_and_order_stable(tmp_path):
    mod = load_script("tt_adherence.py", tmp_path)
    directives = [
        directive(
            "route-docs",
            {"type": "route_followed", "topics": ["heat"], "paths": ["docs/heat.md"]},
        ),
        directive(
            "lint-after-edit",
            {
                "type": "command_after_edit",
                "when_edited": "scripts/*.py",
                "pattern_id": "ruff",
                "pattern": r"ruff check",
            },
        ),
        directive("use-skill", {"type": "skill_used", "topics": ["release"], "skills": ["tt"]}),
        directive("test-first", {"type": "tests_before_commit"}),
        directive("avoid-secrets", {"type": "path_avoided", "forbidden": "secrets/*"}),
        directive("be-clear", {"type": "unobservable", "why": "requires human judgment"}),
    ]
    value = manifest(directives=directives)
    events = [
        {"t": "prompt", "session": "S", "ts": "2026-07-27T10:00:00Z", "topics": ["heat"]},
        {"t": "read", "session": "S", "ts": "2026-07-27T10:01:00Z", "path": "docs/heat.md"},
        {"t": "edit", "session": "S", "ts": "2026-07-27T10:02:00Z", "path": "scripts/a.py"},
        {
            "t": "command",
            "session": "S",
            "ts": "2026-07-27T10:03:00Z",
            "matched": ["ruff"],
        },
        {"t": "test", "session": "S", "ts": "2026-07-27T10:04:00Z", "status": "pass"},
        {"t": "commit", "session": "S", "ts": "2026-07-27T10:05:00Z"},
        {"t": "edit", "session": "S", "ts": "2026-07-27T10:06:00Z", "path": "secrets/a"},
    ]
    result = mod.evaluate(
        events,
        value,
        "2026-07-27T12:00:00Z",
        capture={"topics": True, "commands": True, "edits": True, "commits": True},
        maturity="mature",
    )
    by_id = {item["id"]: item for item in result["directives"]}
    assert by_id["route-docs"]["rate"] == 1.0
    assert by_id["lint-after-edit"]["followed"] == 1
    assert by_id["use-skill"]["status"] == "never-triggered"
    assert by_id["test-first"]["followed"] == 1
    assert by_id["avoid-secrets"]["unobserved"] == 1
    assert by_id["be-clear"] == {
        "id": "be-clear",
        "source": {"file": "CLAUDE.md", "line": 1},
        "status": "unobservable",
        "why": "requires human judgment",
    }
    assert by_id["route-docs"]["trend"] == [
        {"period": "2026-07-27", "opportunities": 1, "followed": 1, "rate": 1.0}
    ]
    assert result["uncertainty"].startswith("unobserved means")


def test_disabled_capture_zero_opportunities_and_compaction(tmp_path):
    mod = load_script("tt_adherence.py", tmp_path)
    value = manifest(
        directives=[
            directive(
                "route-docs",
                {"type": "route_followed", "topics": ["heat"], "paths": ["docs/heat.md"]},
            ),
            directive("test-first", {"type": "tests_before_commit"}),
        ]
    )
    events = [
        {"t": "session", "session": "S", "source": "compact"},
        {"t": "prompt", "session": "S", "ts": "2026-07-27T10:00:00Z", "topics": ["heat"]},
    ]
    disabled = mod.evaluate(events, value, None)
    assert all(item["status"] == "capture-disabled" for item in disabled["directives"])
    compacted = mod.evaluate(
        events,
        value,
        None,
        capture={"topics": True, "commits": True},
    )
    route = next(item for item in compacted["directives"] if item["id"] == "route-docs")
    assert route["opportunities"] == 0
    assert route["degraded_opportunities"] == 1
    assert route["confidence"] == "provisional"
    assert route["evidence"][0]["signal"] == "degraded-after-compaction"
    test = next(item for item in compacted["directives"] if item["id"] == "test-first")
    assert test["status"] == "never-triggered"
    assert test["rate"] is None


def test_probe_negative_and_full_command_paths(tmp_path):
    mod = load_script("tt_adherence.py", tmp_path)
    value = manifest(
        directives=[
            directive(
                "route-docs",
                {"type": "route_followed", "topics": ["heat"], "paths": ["docs/heat.md"]},
            ),
            directive(
                "use-skill",
                {"type": "skill_used", "topics": ["heat"], "skills": ["tt"]},
            ),
            directive(
                "check-before",
                {
                    "type": "command_before_commit",
                    "pattern_id": "check",
                    "pattern": "make check",
                },
            ),
            directive(
                "check-after",
                {
                    "type": "command_after_edit",
                    "when_edited": "*.py",
                    "pattern_id": "lint",
                    "pattern": "ruff check",
                },
            ),
            directive("tests-before", {"type": "tests_before_commit"}),
            directive("avoid", {"type": "path_avoided", "forbidden": "secret/*"}),
        ]
    )
    events = [
        "ignored",
        {"t": "prompt", "session": "S", "ts": "bad", "topics": ["other", 7]},
        {"t": "commit", "session": "S"},
        {"t": "command", "session": "S", "command": "make check"},
        {"t": "edit", "session": "S", "path": "a.py"},
        {"t": "bash", "session": "S", "command": "ruff check ."},
    ]
    result = mod.evaluate(
        events,
        value,
        None,
        capture={"topics": True, "commands": True, "edits": True, "commits": True},
    )
    by_id = {item["id"]: item for item in result["directives"]}
    assert by_id["route-docs"]["status"] == "never-triggered"
    assert by_id["use-skill"]["status"] == "never-triggered"
    assert by_id["check-before"]["unobserved"] == 1
    assert by_id["check-after"]["followed"] == 1
    assert by_id["tests-before"]["unobserved"] == 1
    assert by_id["avoid"]["status"] == "never-triggered"
    assert mod._command_matches({}, {"pattern_id": "x", "pattern": "x"}) is False
    assert mod._capture_enabled("command_after_edit", {"edits": False}) is False
    assert (
        mod._probe_session(
            {"type": "skill_used", "topics": ["heat"], "skills": ["tt"]},
            [
                {"t": "prompt", "topics": ["heat"]},
                {"t": "skill", "skill": "tt"},
            ],
        )
        == "followed"
    )
    assert (
        mod._probe_session(
            {
                "type": "command_before_commit",
                "pattern_id": "check",
                "pattern": "check",
            },
            [],
        )
        is None
    )
    assert (
        mod._probe_session(
            {
                "type": "command_after_edit",
                "when_edited": "*.py",
                "pattern_id": "check",
                "pattern": "check",
            },
            [],
        )
        is None
    )
    with pytest.raises(AssertionError):
        mod._probe_session({"type": "future"}, [])


def test_evidence_cap_manifest_generation_and_cost(tmp_path):
    mod = load_script("tt_adherence.py", tmp_path)
    text = "first directive\nsecond directive\n"
    (tmp_path / "CLAUDE.md").write_bytes(text.encode())
    value = manifest(
        text,
        [
            directive(
                "route-docs",
                {"type": "route_followed", "topics": ["heat"], "paths": ["docs/heat.md"]},
                line=1,
            )
        ],
    )
    expected_hash = mod.manifest_fingerprint(value)
    events = []
    for index in range(7):
        events.append(
            {
                "t": "prompt",
                "session": str(index),
                "ts": f"2026-07-{index + 1:02d}T00:00:00Z",
                "topics": ["heat"],
                "manifest_hash": expected_hash if index else "different-generation",
            }
        )
    result = mod.evaluate(events, value, None, capture={"topics": True}, maturity="mature")
    item = result["directives"][0]
    assert item["opportunities"] == 6
    assert len(item["evidence"]) == mod.MAX_EVIDENCE
    assert item["confidence"] == "mature"
    cost = mod.estimate_cost(value, tmp_path, ["CLAUDE.md"], sessions=7, observed_days=6)
    assert cost["always_loaded_bytes"] == len(text.encode())
    assert cost["sessions_observed"] == 7
    assert cost["directives"][0]["bytes"] == len("first directive\n")
    assert mod.estimate_cost(value, tmp_path)["always_loaded_bytes"] == len(text.encode())
    missing = tmp_path / "missing.md"
    missing.symlink_to(tmp_path / "CLAUDE.md")
    assert mod.estimate_cost(value, tmp_path, ["missing.md"])["always_loaded_bytes"] == 0
    assert mod.estimate_cost(value, tmp_path, ["absent.md"])["always_loaded_bytes"] == 0


def test_instructions_init_missing_report_explain_and_check(tmp_path, monkeypatch, capsys):
    mod = load_script("tt-instructions.py", tmp_path)
    assert mod.main([]) == 0
    assert "--init" in capsys.readouterr().out
    (tmp_path / "CLAUDE.md").write_bytes(b"rules\n")
    assert mod.main(["--init"]) == 0
    created = json.loads((tmp_path / ".trigger-tree" / "directives.json").read_text())
    assert created["instruction_files"][0]["path"] == "CLAUDE.md"
    created["directives"] = [
        directive("be-clear", {"type": "unobservable", "why": "human judgment"})
    ]
    (tmp_path / ".trigger-tree" / "directives.json").write_text(
        json.dumps(created), encoding="utf-8"
    )
    monkeypatch.setattr(
        mod,
        "stats_payload",
        lambda: {
            "adherence": {
                "status": "current",
                "uncertainty": "unobserved means evidence was not captured",
                "summary": {
                    "observable": 0,
                    "unobservable": 1,
                    "capture_disabled": 0,
                },
                "directives": [
                    {
                        "id": "be-clear",
                        "source": {"file": "CLAUDE.md", "line": 1},
                        "status": "unobservable",
                        "why": "human judgment",
                    }
                ],
                "cost": {"headline": "cost headline"},
            }
        },
    )
    assert mod.main([]) == 0
    assert "unobservable" in capsys.readouterr().out
    assert mod.main(["--explain", "be-clear", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["id"] == "be-clear"
    assert mod.main(["--check", "--min-rate", "0.5"]) == 0
    assert "PASS" in capsys.readouterr().out


def test_instructions_cli_error_and_output_branches(tmp_path, monkeypatch, capsys):
    mod = load_script("tt-instructions.py", tmp_path)
    with pytest.raises(mod.tt_adherence.ManifestError, match="no root"):
        mod.init_manifest()
    (tmp_path / "CLAUDE.md").write_text("rules\n")
    assert mod.main(["--init", "--json"]) == 0
    json.loads(capsys.readouterr().out)
    # A second init refreshes hashes and preserves the existing directive list.
    assert mod.main(["--init"]) == 0
    capsys.readouterr()
    stale = {"status": "stale"}
    invalid = {"status": "invalid", "error": "bad"}
    mod._print_report(stale)
    mod._print_report(invalid)
    assert "stale" in capsys.readouterr().out
    with pytest.raises(mod.tt_adherence.ManifestError, match="unknown directive"):
        mod._explain({"directives": []}, "missing")
    with pytest.raises(mod.tt_adherence.ManifestError, match="must be current"):
        mod._check(stale, 0.5)
    measured = {
        "status": "current",
        "uncertainty": "unobserved",
        "summary": {"observable": 3, "unobservable": 0, "capture_disabled": 1},
        "directives": [
            {
                "id": "low",
                "source": {"file": "CLAUDE.md", "line": 1},
                "status": "measured",
                "rate": 0.25,
                "followed": 1,
                "opportunities": 4,
                "unobserved": 3,
                "confidence": "provisional",
                "evidence": [
                    {"session": "S", "ts": None, "result": "unobserved"},
                ],
            },
            {
                "id": "never",
                "source": {"file": "CLAUDE.md", "line": 1},
                "status": "never-triggered",
            },
            {
                "id": "disabled",
                "source": {"file": "CLAUDE.md", "line": 1},
                "status": "capture-disabled",
            },
        ],
        "cost": {"headline": "cost"},
    }
    monkeypatch.setattr(mod, "_adherence", lambda: measured)
    assert mod.main(["--check", "--min-rate", "0.5"]) == 1
    assert "FAIL low" in capsys.readouterr().out
    assert mod.main(["--explain", "low"]) == 0
    assert "time unavailable" in capsys.readouterr().out
    assert mod.main(["--json"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "current"
    mod._print_report(measured)
    output = capsys.readouterr().out
    assert "25%" in output and "never-triggered" in output and "capture-disabled" in output
    monkeypatch.setattr(
        mod,
        "_adherence",
        lambda: (_ for _ in ()).throw(mod.tt_adherence.ManifestError("broken")),
    )
    assert mod.main([]) == 2
    assert "broken" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        mod.main(["--min-rate", "2"])
    with pytest.raises(SystemExit):
        mod.main(["--init", "--check"])


def test_instructions_init_rejects_symlinked_telemetry(tmp_path):
    mod = load_script("tt-instructions.py", tmp_path)
    (tmp_path / "CLAUDE.md").write_text("rules\n")
    target = tmp_path / "telemetry-target"
    target.mkdir()
    try:
        (tmp_path / ".trigger-tree").symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation is unavailable")
    with pytest.raises(mod.tt_adherence.ManifestError, match="symlinked"):
        mod.init_manifest()


def test_instructions_stats_subprocess_failures(tmp_path, monkeypatch):
    mod = load_script("tt-instructions.py", tmp_path)

    def completed(returncode=0, stdout="{}", stderr=""):
        return subprocess.CompletedProcess([], returncode, stdout, stderr)

    monkeypatch.setattr(mod.subprocess, "run", lambda *args, **kwargs: completed(1, stderr="no"))
    with pytest.raises(mod.tt_adherence.ManifestError, match="no"):
        mod.stats_payload()
    monkeypatch.setattr(mod.subprocess, "run", lambda *args, **kwargs: completed(stdout="{"))
    with pytest.raises(mod.tt_adherence.ManifestError, match="invalid JSON"):
        mod.stats_payload()


def test_stats_adherence_is_additive_and_stale_is_not_evaluated(tmp_path, monkeypatch):
    (tmp_path / "CLAUDE.md").write_bytes(b"rules\n")
    stats_mod = load_script("tt-stats.py", tmp_path)

    def run():
        stream = io.StringIO()
        monkeypatch.setattr(sys, "argv", ["tt-stats.py"])
        monkeypatch.setattr(sys, "stdout", stream)
        stats_mod.main()
        return json.loads(stream.getvalue())

    baseline = run()
    assert "adherence" not in baseline
    telemetry = tmp_path / ".trigger-tree"
    telemetry.mkdir()
    value = manifest("rules\n", [directive("be-clear", {"type": "unobservable", "why": "x"})])
    (telemetry / "directives.json").write_text(json.dumps(value))
    current = run()
    assert current["adherence"]["status"] == "current"
    assert current["adherence"]["cost"]["estimated_tokens_per_session"] > 0
    (tmp_path / "CLAUDE.md").write_text("changed\n")
    assert run()["adherence"]["status"] == "stale"
    (telemetry / "directives.json").write_text("{}")
    assert run()["adherence"]["status"] == "invalid"
