import io
import json
import os
import sys

import pytest
from conftest import FIXTURE, load_script


def run_stats(mod, monkeypatch, argv=None):
    out = io.StringIO()
    monkeypatch.setattr(sys, "argv", ["tt-stats.py"] + (argv or []))
    monkeypatch.setattr(sys, "stdout", out)
    mod.main()
    return json.loads(out.getvalue())


def write_history(project, lines):
    d = project / ".trigger-tree"
    d.mkdir(exist_ok=True)
    (d / "history.jsonl").write_text("\n".join(json.dumps(line) for line in lines) + "\n")


def test_pure_helpers():
    mod = load_script("tt-stats.py", FIXTURE)
    assert mod.parse_ts("2026-07-01T09:00:00Z").year == 2026
    assert mod.parse_ts("garbage") is None and mod.parse_ts(None) is None
    assert mod.observed_days(["2026-07-01T00:00:00Z", "2026-07-02T00:00:00Z"]) == 1.0
    assert mod.observed_days(["bad", "also-bad"]) == 0.0
    assert mod.jaccard([], []) == 0.0
    assert mod.jaccard(["a", "b"], ["a", "c"]) == 1 / 3
    assert mod.fingerprint(["b", "a"]) == mod.fingerprint(["a", "b"])
    assert mod._conf_regex("TT_MISSING", r"^fallback$").pattern == "^fallback$"
    assert mod._conf_value("TT_MISSING", "fallback") == "fallback"
    assert [mod.grade_for(x) for x in (95, 80, 65, 50, 10)] == ["A", "B", "C", "D", "F"]
    assert mod.badge_payload({"grade": "A", "score": 96}, "warming") == {
        "schemaVersion": 1,
        "label": "docs health",
        "message": "measuring…",
        "color": "lightgrey",
    }
    expected_colors = {"A": "brightgreen", "B": "green", "C": "yellow", "D": "orange", "F": "red"}
    for grade, color in expected_colors.items():
        assert mod.badge_payload({"grade": grade, "score": 82}, "mature") == {
            "schemaVersion": 1,
            "label": "docs health",
            "message": f"{grade} (82)",
            "color": color,
        }


def test_badge_mode_writes_private_endpoint_json(tmp_path, monkeypatch, capsys):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "README.md").write_text("router")
    mod = load_script("tt-stats.py", tmp_path)
    monkeypatch.setattr(sys, "argv", ["tt-stats.py", "--badge"])
    mod.main()
    output = capsys.readouterr().out.strip()
    badge = tmp_path / ".trigger-tree" / "badge.json"
    assert output == str(badge)
    assert json.loads(badge.read_text()) == {
        "schemaVersion": 1,
        "label": "docs health",
        "message": "measuring…",
        "color": "lightgrey",
    }
    assert badge.stat().st_mode & 0o777 == 0o600


def test_badge_refuses_symlinked_telemetry_directory(tmp_path):
    mod = load_script("tt-stats.py", tmp_path)
    target = tmp_path / "outside"
    target.mkdir()
    try:
        (tmp_path / ".trigger-tree").symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation is unavailable")
    with pytest.raises(RuntimeError, match="symlinked"):
        mod.write_badge({})


def test_client_detection_and_prompt_filters(monkeypatch):
    mod = load_script("tt-stats.py", FIXTURE)
    monkeypatch.delenv("CLAUDE_PLUGIN_ROOT", raising=False)
    monkeypatch.delenv("CODEX_HOME", raising=False)
    monkeypatch.delenv("PLUGIN_ROOT", raising=False)
    assert mod.detect_client() is None
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", "/plugin")
    assert mod.detect_client() == "claude"
    monkeypatch.delenv("CLAUDE_PLUGIN_ROOT")
    monkeypatch.setenv("CODEX_HOME", "/codex")
    assert mod.detect_client() == "codex"
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", "/compat")
    assert mod.detect_client() == "codex"
    assert mod.detect_client("claude") == "claude"

    assert mod.prompt_preview({}, "claude", "previous") == "previous"
    assert mod.prompt_preview({"prompt": "#abc", "prompt_hash": True}, "claude") == ""
    assert mod.prompt_preview({"prompt": "git status"}, "claude", "task") == "task"
    assert mod.prompt_preview({"prompt": "<environment_context>x"}, "codex", "task") == "task"


def test_router_coverage_uses_existing_index_and_ignores_unrelated_inlinks(tmp_path, monkeypatch):
    architecture = tmp_path / "docs" / "architecture"
    other = tmp_path / "docs" / "other"
    architecture.mkdir(parents=True)
    other.mkdir(parents=True)
    (architecture / "_index.md").write_text("- [Listed](listed.md)\n")
    (architecture / "listed.md").write_text("Listed\n")
    (architecture / "unlisted.md").write_text("Unlisted\n")
    (other / "reference.md").write_text("See ../architecture/unlisted.md\n")
    write_history(tmp_path, [{"t": "session", "session": "S"}])

    mod = load_script("tt-stats.py", tmp_path)
    stats = run_stats(mod, monkeypatch)
    coverage = {item["folder"]: item for item in stats["router_coverage"]}

    assert coverage["docs/architecture"] == {
        "folder": "docs/architecture",
        "router": "docs/architecture/_index.md",
        "files": 2,
        "listed": 1,
        "unlisted": ["docs/architecture/unlisted.md"],
    }
    detail = {item["path"]: item for item in stats["untouched_detail"]}
    assert detail["docs/architecture/_index.md"]["is_router"] is True
    assert detail["docs/architecture/_index.md"]["template"] is False
    assert detail["docs/architecture/_index.md"]["router_mentions_target"] is True
    assert detail["docs/architecture/unlisted.md"]["referenced_from"] == ["docs/other/reference.md"]
    assert detail["docs/architecture/unlisted.md"]["router_mentions_target"] is False


def test_search_activity_distinguishes_concentrated_and_distributed_sessions(tmp_path, monkeypatch):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "README.md").write_text("Docs\n")
    events = []
    for number in range(10):
        session = f"S{number}"
        events.append({"t": "session", "session": session})
        if number < 2:
            events.extend(
                {"t": "scan", "session": session, "path": "docs/bulk", "tool": "Bash"}
                for _ in range(4)
            )
        if number < 6:
            events.append(
                {"t": "scan", "session": session, "path": "docs/repeated", "tool": "Grep"}
            )
    write_history(tmp_path, events)

    mod = load_script("tt-stats.py", tmp_path)
    stats = run_stats(mod, monkeypatch)
    activity = {item["path"]: item for item in stats["hunting"]}
    assert stats["search_activity"] == stats["hunting"]

    assert activity["docs/bulk"] == {
        "path": "docs/bulk",
        "scans": 8,
        "sessions": 2,
        "total_sessions": 10,
        "session_reach": 0.2,
        "max_session_share": 0.5,
        "tools": {"Bash": 8},
        "pattern": "concentrated",
    }
    assert activity["docs/repeated"]["pattern"] == "distributed"
    assert activity["docs/repeated"]["tools"] == {"Grep": 6}


def test_temporal_heat_decays_reheats_and_keeps_lifetime_reads(tmp_path, monkeypatch):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.md").write_text("a")
    (tmp_path / "docs" / "b.md").write_text("b")
    write_history(
        tmp_path,
        [
            {"t": "read", "session": "S", "path": "docs/a.md", "ts": "2026-07-20T12:00:00Z"},
            {"t": "read", "session": "S", "path": "docs/a.md", "ts": "2026-06-20T12:00:00Z"},
            {"t": "read", "session": "S", "path": "docs/a.md", "ts": "2026-04-21T12:00:00Z"},
            {"t": "read", "session": "S", "path": "docs/a.md", "ts": "2025-07-20T12:00:00Z"},
            {"t": "read", "session": "S", "path": "docs/a.md"},
            # Clock skew cannot make a read contribute more than one unit.
            {"t": "read", "session": "S", "path": "docs/b.md", "ts": "2026-07-21T12:00:00Z"},
        ],
    )
    mod = load_script("tt-stats.py", tmp_path)
    now = mod.parse_ts("2026-07-20T12:00:00Z")
    monkeypatch.setattr(mod, "utc_now", lambda: now)
    stats = run_stats(mod, monkeypatch)
    files = {item["path"]: item for item in stats["files"]}

    assert files["docs/a.md"]["reads"] == 5
    assert files["docs/a.md"]["heat"] == 1.625
    assert files["docs/a.md"]["heat_scored_reads"] == 4
    assert [files["docs/a.md"][f"reads_{days}d"] for days in (7, 30, 90)] == [1, 2, 3]
    assert files["docs/b.md"]["heat"] == 1.0
    assert stats["heat_model"] == {
        "kind": "exponential_decay",
        "half_life_days": 30.0,
        "as_of": "2026-07-20T12:00:00Z",
        "windows_days": [7, 30, 90],
        "untimestamped_reads": 1,
    }
    folder = stats["folders"][0]
    assert folder["reads"] == 6 and folder["heat"] == 2.625
    assert folder["reads_30d"] == 3 and folder["last_read"] == "2026-07-21T12:00:00Z"


def test_broken_project_config_falls_back_to_plugin_default(tmp_path, monkeypatch):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.md").write_text("x")
    (tmp_path / ".trigger-tree").mkdir()
    (tmp_path / ".trigger-tree" / "config.sh").write_text("TT_WATCH_REGEX='([broken'\n")
    mod = load_script("tt-stats.py", tmp_path)  # must not crash on the invalid regex
    assert mod.WATCH.search("docs/a.md") and mod.WATCH.search("agents/x.md")


def test_load_events_skips_torn_lines(tmp_path):
    mod = load_script("tt-stats.py", tmp_path)
    p = tmp_path / "h.jsonl"
    p.write_text('{"t":"read","path":"docs/a.md"}\n{{{torn\n\n{"t":"scan","path":"docs"}\n')
    events = mod.load_events([str(p), str(tmp_path / "missing.jsonl")])
    assert [e["t"] for e in events] == ["read", "scan"]
    assert all(event["schema_version"] == 1 and event["migrated_from"] == 0 for event in events)


@pytest.mark.skipif(os.name == "nt", reason="symlink creation needs elevated rights on Windows")
def test_inventory_and_history_never_follow_symlinks(tmp_path, monkeypatch):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "real.md").write_text("real")
    outside_doc = tmp_path / "outside.md"
    outside_doc.write_text("external")
    (tmp_path / "docs" / "linked.md").symlink_to(outside_doc)
    telemetry = tmp_path / ".trigger-tree"
    telemetry.mkdir()
    outside_history = tmp_path / "outside.jsonl"
    outside_history.write_text('{"t":"read","path":"docs/real.md"}\n')
    (telemetry / "history.jsonl").symlink_to(outside_history)

    mod = load_script("tt-stats.py", tmp_path)
    stats = run_stats(mod, monkeypatch)

    assert mod.inventory() == ["docs/real.md"]
    assert stats["totals"]["reads"] == 0


def test_history_schema_migrates_legacy_and_rejects_future(tmp_path):
    mod = load_script("tt-stats.py", tmp_path)
    path = tmp_path / "history.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps({"t": "session", "session": "legacy"}),
                json.dumps({"schema_version": 1, "t": "session", "session": "current"}),
                json.dumps({"schema_version": 99, "t": "read", "path": "docs/future.md"}),
                "[]",
                "{torn",
            ]
        )
        + "\n"
    )
    events, diagnostics = mod.load_events_with_diagnostics([str(path)])
    assert [event["session"] for event in events] == ["legacy", "current"]
    assert events[0]["migrated_from"] == 0
    assert diagnostics == {"legacy_migrated": 1, "future_rejected": 1, "corrupt_lines": 2}


def test_history_schema_rejects_structurally_invalid_current_events(tmp_path):
    mod = load_script("tt-stats.py", tmp_path)
    path = tmp_path / "history.jsonl"
    path.write_text(
        "\n".join(
            json.dumps(event)
            for event in (
                {"schema_version": 1, "t": "read", "session": "S"},
                {"schema_version": 1, "t": "scan", "path": ""},
                {"schema_version": 1, "t": "skill"},
                {"schema_version": 1, "t": "session", "ts": 42},
                {"schema_version": 1, "t": "invented"},
                {"schema_version": 1, "t": "read", "path": "docs/valid.md"},
            )
        )
        + "\n"
    )

    events, diagnostics = mod.load_events_with_diagnostics([str(path)])

    assert events == [{"schema_version": 1, "t": "read", "path": "docs/valid.md"}]
    assert diagnostics["corrupt_lines"] == 5


def test_co_read_pairs_skip_oversized_prompt_buckets(tmp_path, monkeypatch):
    (tmp_path / "docs").mkdir()
    events = [{"t": "prompt", "session": "S", "prompt": "Review all docs"}]
    for index in range(201):
        path = f"docs/{index}.md"
        (tmp_path / path).write_text("x")
        events.append({"t": "read", "session": "S", "path": path})
    write_history(tmp_path, events)

    mod = load_script("tt-stats.py", tmp_path)
    stats = run_stats(mod, monkeypatch)

    assert stats["co_read_top"] == []
    assert stats["co_read_diagnostics"] == {
        "max_paths_per_prompt": 200,
        "oversized_prompts_skipped": 1,
    }


def test_recursive_claude_imports_are_always_loaded_not_cold(tmp_path, monkeypatch):
    (tmp_path / "docs" / "rules").mkdir(parents=True)
    (tmp_path / "CLAUDE.md").write_text(
        "Project context: @docs/router.md @https://example.com/external.md @docs/missing.md\n"
    )
    (tmp_path / "docs" / "router.md").write_text("Nested rules: @rules/critical.md @../CLAUDE.md\n")
    (tmp_path / "docs" / "rules" / "critical.md").write_text(
        "Never expose secrets. @../../../outside.md\n"
    )
    (tmp_path / "docs" / "unused.md").write_text("Unused.\n")
    write_history(tmp_path, [{"t": "session", "session": "S", "ts": "2026-07-01T00:00:00Z"}])

    mod = load_script("tt-stats.py", tmp_path)
    stats = run_stats(mod, monkeypatch)

    assert stats["always_loaded_imports"] == [
        "CLAUDE.md",
        "docs/router.md",
        "docs/rules/critical.md",
    ]
    assert "docs/router.md" in stats["always_loaded"]
    assert "docs/rules/critical.md" in stats["always_loaded"]
    assert "docs/router.md" not in stats["untouched"]
    assert "docs/rules/critical.md" not in {item["path"] for item in stats["untouched_detail"]}
    assert stats["untouched"] == ["docs/unused.md"]


def test_unreadable_claude_file_does_not_break_import_graph(tmp_path, monkeypatch):
    (tmp_path / "CLAUDE.md").write_text("@docs/a.md")
    mod = load_script("tt-stats.py", tmp_path)

    def unreadable(*_args, **_kwargs):
        raise OSError("permission denied")

    monkeypatch.setattr("builtins.open", unreadable)
    assert mod.claude_import_graph(["CLAUDE.md", "docs/a.md"]) == {"CLAUDE.md"}


def test_subagent_reads_count_and_compaction_replay_is_deduplicated(tmp_path, monkeypatch):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.md").write_text("x")
    duplicate = {
        "t": "read",
        "ts": "2026-07-01T09:00:00Z",
        "session": "S",
        "tool": "Read",
        "tool_use_id": "toolu-1",
        "path": "docs/a.md",
        "agent": "Explore",
        "agent_id": "agent-1",
    }
    history_dir = tmp_path / ".trigger-tree"
    history_dir.mkdir()
    (history_dir / "history-20260701-090000.jsonl").write_text(json.dumps(duplicate) + "\n")
    (history_dir / "history.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"t": "session", "session": "S", "source": "compact"}),
                json.dumps(duplicate),
            ]
        )
        + "\n"
    )

    mod = load_script("tt-stats.py", tmp_path)
    stats = run_stats(mod, monkeypatch)

    assert stats["totals"]["reads"] == 1
    assert stats["files"][0]["reads"] == 1
    assert stats["files"][0]["agents"] == {"Explore": 1}
    assert stats["signal_integrity"] == {
        "subagent_reads": "captured",
        "subagent_read_events": 1,
        "compaction_boundaries": 1,
    }


def test_rare_critical_docs_are_protected_review_items(tmp_path, monkeypatch):
    (tmp_path / ".claude" / "rules").mkdir(parents=True)
    (tmp_path / "docs" / "security").mkdir(parents=True)
    (tmp_path / "docs" / "decisions").mkdir(parents=True)
    (tmp_path / ".trigger-tree").mkdir()
    (tmp_path / ".trigger-tree" / "config.sh").write_text("TT_CRITICAL_GLOB='docs/decisions/**'\n")
    (tmp_path / ".claude" / "rules" / "production.md").write_text("Never deploy without review.")
    (tmp_path / "docs" / "security" / "incident.md").write_text("Escalation policy.")
    (tmp_path / "docs" / "decisions" / "adr.md").write_text("critical: true\n")
    write_history(tmp_path, [{"t": "session", "session": "S"}])

    mod = load_script("tt-stats.py", tmp_path)
    stats = run_stats(mod, monkeypatch)
    items = {item["path"]: item for item in stats["review_candidates"]}

    rule = items[".claude/rules/production.md"]
    assert rule["classification"] == "protected"
    assert rule["recommendation"] == "review, likely keep — rare-but-critical"
    assert "safety path" in rule["why"]
    assert "Low reads can mean rare-but-critical" in rule["caveat"]
    assert "safety path" in items["docs/security/incident.md"]["why"]
    assert "critical glob docs/decisions/**" in items["docs/decisions/adr.md"]["why"]


def test_critical_tag_is_protected_without_other_protection(tmp_path, monkeypatch):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "recovery.md").write_text("critical: true\n")
    write_history(tmp_path, [{"t": "session", "session": "S"}])

    mod = load_script("tt-stats.py", tmp_path)
    stats = run_stats(mod, monkeypatch)
    items = {item["path"]: item for item in stats["review_candidates"]}

    recovery = items["docs/recovery.md"]
    assert recovery["classification"] == "protected"
    assert recovery["recommendation"] == "review, likely keep — rare-but-critical"
    assert recovery["why"] == ["tagged critical"]


def test_widely_linked_file_is_protected_at_in_link_threshold(tmp_path, monkeypatch):
    (tmp_path / "docs" / "refs").mkdir(parents=True)
    (tmp_path / "docs" / "contract.md").write_text("Stable contract.")
    for index in range(3):
        (tmp_path / "docs" / "refs" / f"{index}.md").write_text("See ../contract.md")
    write_history(tmp_path, [{"t": "session", "session": "S"}])

    mod = load_script("tt-stats.py", tmp_path)
    stats = run_stats(mod, monkeypatch)
    items = {item["path"]: item for item in stats["review_candidates"]}

    contract = items["docs/contract.md"]
    assert contract["classification"] == "protected"
    assert contract["recommendation"] == "review, likely keep — rare-but-critical"
    assert contract["why"] == ["referenced by 3 other docs"]


def test_experimental_outcome_view_is_correlational_and_flagged(tmp_path, monkeypatch):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.md").write_text("a")
    (tmp_path / "docs" / "b.md").write_text("b")
    config = tmp_path / ".trigger-tree"
    config.mkdir()
    (config / "config.sh").write_text("TT_EXPERIMENTAL_OUTCOMES='on'\n")
    write_history(
        tmp_path,
        [
            {"t": "read", "session": "committed", "path": "docs/a.md"},
            {"t": "outcome", "session": "committed", "git_commit_landed": True},
            {"t": "read", "session": "abandoned", "path": "docs/b.md"},
            {"t": "outcome", "session": "abandoned", "git_commit_landed": False},
            {"t": "read", "session": "open", "path": "docs/a.md"},
        ],
    )
    mod = load_script("tt-stats.py", tmp_path)
    outcomes = run_stats(mod, monkeypatch)["experimental_outcomes"]
    assert outcomes["label"] == "experimental correlation — not causal"
    assert outcomes["committed"] == {
        "sessions": 1,
        "docs": [{"path": "docs/a.md", "reads": 1}],
    }
    assert outcomes["abandoned"] == {
        "sessions": 1,
        "docs": [{"path": "docs/b.md", "reads": 1}],
    }


def test_experimental_outcomes_are_off_by_default(tmp_path, monkeypatch):
    mod = load_script("tt-stats.py", tmp_path)
    assert run_stats(mod, monkeypatch)["experimental_outcomes"] is None


def test_fixture_full_run(monkeypatch):
    mod = load_script("tt-stats.py", FIXTURE)
    s = run_stats(mod, monkeypatch)
    assert s["maturity"] == "cold-start"
    assert (
        s["totals"]["reads"] == 17 and s["totals"]["scans"] == 2 and s["totals"]["skill_uses"] == 1
    )
    assert s["totals"]["inventory_files"] == 34
    assert s["sessions"] == 4
    assert len(s["untouched"]) == 19, s["untouched"]
    for p in (
        "docs/architecture/decisions/001-event-sourcing.md",
        "docs/development/testing.md",
        "docs/security/threat-model.md",
        "docs/operations/runbooks/incident-response.md",
        "agents/security-engineer.md",
        "skills/doc-update.md",
    ):
        assert p in s["untouched"], p
    assert s["always_loaded"] == ["AGENTS.md", "CLAUDE.md"]  # invoked skill's SKILL.md excluded
    assert s["always_loaded_inventory"] == [
        ".claude/skills/deploy/SKILL.md",
        "AGENTS.md",
        "CLAUDE.md",
    ]
    assert (
        s["totals"]["touched_current_files"] + s["totals"]["untouched_current_files"]
        == s["totals"]["evaluable_files"]
    )
    assert s["files"][0]["path"] == "docs/README.md" and s["files"][0]["reads"] == 3
    assert s["skills"][0] == {
        "name": "deploy",
        "uses": 1,
        "sessions": 1,
        "last_used": "2026-07-01T09:05:00Z",
    }
    assert len(s["trend"]) == 4 and s["trend"][0]["search_ratio"] == 0.2
    assert s["trend"][0]["hunting_ratio"] == 0.2  # compatibility alias
    assert s["notes"] == [{"ts": "2026-07-01T10:00:00Z", "text": "sharpened UX router"}]
    # three task clusters: UX (2 similar sessions merged via Jaccard), database, incident
    assert len(s["clusters"]) == 3, s["clusters"]
    assert s["clusters"][0]["count"] == 2 and s["clusters"][0]["variants"] == 2
    assert "docs/design/ui-patterns.md" in s["clusters"][0]["paths"]
    assert {"pair": ["docs/README.md", "docs/design/ui-patterns.md"], "count": 2} in s[
        "co_read_top"
    ]

    assert s["health"] == {
        "score": 56,
        "grade": "D",
        "coverage": 0.39,
        "drivers": [
            "19 of 31 evaluable docs untouched",
            "12 router gaps (untouched and unreferenced)",
            "distributed search ratio 0.0",
        ],
    }

    # router-gap detection: accessibility.md is untouched AND unreferenced;
    # workflow.md is untouched but development/index.md mentions it
    detail = {d["path"]: d for d in s["untouched_detail"]}
    assert detail["docs/design/accessibility.md"]["referenced_from"] == []
    assert "docs/development/index.md" in detail["docs/development/workflow.md"]["referenced_from"]
    assert detail["docs/architecture/decisions/_template.md"]["template"] is True
    assert detail["docs/design/accessibility.md"]["template"] is False

    # folder heat/cold map: design 3/4 touched, security fully cold, runbooks 1/2
    folders = {f["folder"]: f for f in s["folders"]}
    assert folders["docs/design"]["touched"] == 3 and folders["docs/design"]["coverage"] == 0.75
    assert folders["docs/design"]["has_index"] is True
    assert folders["docs/architecture/decisions"]["has_index"] is False
    assert folders["docs/security"]["coverage"] == 0.0
    assert folders["docs/operations/runbooks"]["touched"] == 1
    assert folders["docs/README.md".rsplit("/", 1)[0]]["reads"] == 3  # docs/ root folder


def _bulk_events(reads, sessions, days):
    events = []
    for i in range(reads):
        day = 1 + (i * days) // reads
        session = f"S{i % sessions}"
        events.append(
            {
                "t": "read",
                "ts": f"2026-07-{day:02d}T09:{i % 60:02d}:00Z",
                "session": session,
                "tool": "Read",
                "path": "docs/a.md",
                "agent": "main",
            }
        )
    return events


def test_maturity_warming(tmp_path, monkeypatch):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.md").write_text("x")
    write_history(tmp_path, _bulk_events(reads=40, sessions=3, days=2))
    mod = load_script("tt-stats.py", tmp_path)
    assert run_stats(mod, monkeypatch)["maturity"] == "warming"


def test_maturity_mature_and_weekly_trend(tmp_path, monkeypatch):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.md").write_text("x")
    write_history(tmp_path, _bulk_events(reads=120, sessions=3, days=20))
    mod = load_script("tt-stats.py", tmp_path)
    s = run_stats(mod, monkeypatch)
    assert s["maturity"] == "mature"
    assert all("W" in b["period"] for b in s["trend"])  # weekly buckets beyond 14 days


def test_unknown_reads_and_explicit_history(tmp_path, monkeypatch):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.md").write_text("x")
    write_history(
        tmp_path,
        [
            {
                "t": "read",
                "ts": "2026-07-01T09:00:00Z",
                "session": "A",
                "tool": "Read",
                "path": "docs/ghost.md",
                "agent": "main",
            }
        ],
    )
    mod = load_script("tt-stats.py", tmp_path)
    explicit = str(tmp_path / ".trigger-tree" / "history.jsonl")
    s = run_stats(mod, monkeypatch, [explicit])
    assert s["unknown_reads"] == []
    assert s["retired_files"][0]["path"] == "docs/ghost.md"
    assert s["untouched"] == ["docs/a.md"]


def test_retired_paths_do_not_affect_current_heat_or_coverage(tmp_path, monkeypatch):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "current.md").write_text("current")
    write_history(
        tmp_path,
        [
            {"t": "read", "session": "S", "path": "docs/retired.md", "agent": "feature"},
            {"t": "read", "session": "S", "path": "docs/current.md", "agent": "main"},
        ],
    )

    mod = load_script("tt-stats.py", tmp_path)
    stats = run_stats(mod, monkeypatch)
    files = {item["path"]: item for item in stats["files"]}

    assert files["docs/retired.md"]["state"] == "retired"
    assert files["docs/current.md"]["state"] == "current"
    assert stats["totals"]["touched_current_files"] == 1
    assert stats["totals"]["untouched_current_files"] == 0
    assert stats["retired_files"][0]["agents"] == {"feature": 1}
    folder = next(item for item in stats["folders"] if item["folder"] == "docs")
    assert folder["retired_reads"] == 1
    assert folder["retired_read_share"] == 0.5


def test_missing_file_age_stat_does_not_break_folder_metrics(tmp_path, monkeypatch):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.md").write_text("a")
    write_history(tmp_path, [{"t": "read", "session": "S", "path": "docs/a.md"}])

    mod = load_script("tt-stats.py", tmp_path)
    monkeypatch.setattr(mod.os.path, "getmtime", lambda _path: (_ for _ in ()).throw(OSError()))
    stats = run_stats(mod, monkeypatch)

    assert stats["folders"][0]["median_file_age_days"] is None


def test_reference_count_and_sample_use_one_full_source(tmp_path, monkeypatch):
    (tmp_path / "docs" / "refs").mkdir(parents=True)
    (tmp_path / "docs" / "target.md").write_text("target")
    for index in range(7):
        (tmp_path / "docs" / "refs" / f"{index}.md").write_text("../target.md")
    write_history(tmp_path, [{"t": "session", "session": "S"}])

    mod = load_script("tt-stats.py", tmp_path)
    stats = run_stats(mod, monkeypatch)
    item = next(row for row in stats["review_candidates"] if row["path"] == "docs/target.md")

    assert item["inbound_refs"] == 7
    assert len(item["referenced_from"]) == 7
    assert item["referenced_from_sample"] == item["referenced_from"][:5]
    assert item["why"] == ["referenced by 7 other docs"]


def test_cluster_prompts_filter_client_envelopes_and_use_real_fallback(tmp_path, monkeypatch):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.md").write_text("a")
    write_history(
        tmp_path,
        [
            {"t": "prompt", "session": "S", "prompt": "Review the routing docs"},
            {"t": "read", "session": "S", "path": "docs/a.md"},
            {
                "t": "prompt",
                "session": "S",
                "prompt": "<task-notification>done</task-notification>",
            },
            {"t": "read", "session": "S", "path": "docs/a.md"},
            {"t": "prompt", "session": "T", "prompt": "/tt watch"},
            {"t": "read", "session": "T", "path": "docs/a.md"},
        ],
    )

    mod = load_script("tt-stats.py", tmp_path)
    stats = run_stats(mod, monkeypatch, ["--client", "claude"])
    prompts = [prompt for cluster in stats["clusters"] for prompt in cluster["prompts"]]

    assert prompts == ["Review the routing docs", "Review the routing docs"]
    assert all("task-notification" not in prompt and "/tt" not in prompt for prompt in prompts)


def test_two_prompts_in_one_session_make_two_buckets(tmp_path, monkeypatch):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.md").write_text("x")
    (tmp_path / "docs" / "b.md").write_text("x")
    write_history(
        tmp_path,
        [
            {"t": "prompt", "ts": "2026-07-01T09:00:00Z", "session": "A", "prompt": "task one"},
            {
                "t": "read",
                "ts": "2026-07-01T09:00:10Z",
                "session": "A",
                "tool": "Read",
                "path": "docs/a.md",
                "agent": "main",
            },
            {"t": "prompt", "ts": "2026-07-01T09:05:00Z", "session": "A", "prompt": "task two"},
            {
                "t": "read",
                "ts": "2026-07-01T09:05:10Z",
                "session": "A",
                "tool": "Read",
                "path": "docs/b.md",
                "agent": "main",
            },
        ],
    )
    mod = load_script("tt-stats.py", tmp_path)
    s = run_stats(mod, monkeypatch)
    assert s["totals"]["prompts_with_doc_reads"] == 2
    assert len(s["clusters"]) == 2  # disjoint sets don't cluster together


def test_unreadable_doc_does_not_break_crossref(tmp_path, monkeypatch):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.md").write_text("x")
    locked = tmp_path / "docs" / "locked.md"
    locked.write_text("secret")
    write_history(
        tmp_path,
        [
            {
                "t": "read",
                "ts": "2026-07-01T09:00:00Z",
                "session": "A",
                "tool": "Read",
                "path": "docs/a.md",
                "agent": "main",
            }
        ],
    )
    mod = load_script("tt-stats.py", tmp_path)
    real_open = open

    def fail_locked(path, *args, **kwargs):
        if str(path).endswith("locked.md"):
            raise OSError("permission denied")
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr("builtins.open", fail_locked)
    s = run_stats(mod, monkeypatch)
    assert "docs/locked.md" in s["untouched"]  # unreadable file still analyzed


def test_trend_skips_unparseable_timestamps(tmp_path, monkeypatch):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.md").write_text("x")
    write_history(
        tmp_path,
        [
            {
                "t": "read",
                "ts": "not-a-ts",
                "session": "A",
                "tool": "Read",
                "path": "docs/a.md",
                "agent": "main",
            },
            {
                "t": "read",
                "ts": "2026-07-01T09:00:00Z",
                "session": "A",
                "tool": "Read",
                "path": "docs/a.md",
                "agent": "main",
            },
        ],
    )
    mod = load_script("tt-stats.py", tmp_path)
    s = run_stats(mod, monkeypatch)
    assert len(s["trend"]) == 1 and s["trend"][0]["reads"] == 1
