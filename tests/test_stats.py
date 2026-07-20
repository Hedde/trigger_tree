import io
import json
import sys

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
    assert s["files"][0]["path"] == "docs/README.md" and s["files"][0]["reads"] == 3
    assert s["skills"][0] == {
        "name": "deploy",
        "uses": 1,
        "sessions": 1,
        "last_used": "2026-07-01T09:05:00Z",
    }
    assert len(s["trend"]) == 4 and s["trend"][0]["hunting_ratio"] == 0.2
    assert s["notes"] == [{"ts": "2026-07-01T10:00:00Z", "text": "sharpened UX router"}]
    # three task clusters: UX (2 similar sessions merged via Jaccard), database, incident
    assert len(s["clusters"]) == 3, s["clusters"]
    assert s["clusters"][0]["count"] == 2 and s["clusters"][0]["variants"] == 2
    assert "docs/design/ui-patterns.md" in s["clusters"][0]["paths"]
    assert {"pair": ["docs/README.md", "docs/design/ui-patterns.md"], "count": 2} in s[
        "co_read_top"
    ]

    assert s["health"] == {
        "score": 50,
        "grade": "D",
        "coverage": 0.41,
        "drivers": [
            "19 of 34 docs untouched",
            "12 router gaps (untouched and unreferenced)",
            "hunting ratio 0.12",
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
    assert s["unknown_reads"] == ["docs/ghost.md"]
    assert s["untouched"] == ["docs/a.md"]


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
