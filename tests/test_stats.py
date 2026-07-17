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
    (d / "history.jsonl").write_text("\n".join(json.dumps(l) for l in lines) + "\n")


def test_pure_helpers():
    mod = load_script("tt-stats.py", FIXTURE)
    assert mod.parse_ts("2026-07-01T09:00:00Z").year == 2026
    assert mod.parse_ts("garbage") is None and mod.parse_ts(None) is None
    assert mod.observed_days(["2026-07-01T00:00:00Z", "2026-07-02T00:00:00Z"]) == 1.0
    assert mod.observed_days(["bad", "also-bad"]) == 0.0
    assert mod.jaccard([], []) == 0.0
    assert mod.jaccard(["a", "b"], ["a", "c"]) == 1 / 3
    assert mod.fingerprint(["b", "a"]) == mod.fingerprint(["a", "b"])
    assert mod._conf_regex("nothing here", "TT_MISSING", r"^fallback$").pattern == "^fallback$"
    assert [mod.grade_for(x) for x in (95, 80, 65, 50, 10)] == ["A", "B", "C", "D", "F"]


def test_load_events_skips_torn_lines(tmp_path):
    mod = load_script("tt-stats.py", tmp_path)
    p = tmp_path / "h.jsonl"
    p.write_text('{"t":"read","path":"docs/a.md"}\n{{{torn\n\n{"t":"scan","path":"docs"}\n')
    events = mod.load_events([str(p), str(tmp_path / "missing.jsonl")])
    assert [e["t"] for e in events] == ["read", "scan"]


def test_fixture_full_run(monkeypatch):
    mod = load_script("tt-stats.py", FIXTURE)
    s = run_stats(mod, monkeypatch)
    assert s["maturity"] == "cold-start"
    assert s["totals"]["reads"] == 17 and s["totals"]["scans"] == 2 and s["totals"]["skill_uses"] == 1
    assert s["totals"]["inventory_files"] == 33
    assert s["sessions"] == 4
    assert len(s["untouched"]) == 18, s["untouched"]
    for p in ("docs/architecture/decisions/001-event-sourcing.md",
              "docs/development/testing.md", "docs/security/threat-model.md",
              "docs/operations/runbooks/incident-response.md",
              "agents/security-engineer.md", "skills/doc-update.md"):
        assert p in s["untouched"], p
    assert s["always_loaded"] == ["AGENTS.md", "CLAUDE.md"]  # invoked skill's SKILL.md excluded
    assert s["files"][0]["path"] == "docs/README.md" and s["files"][0]["reads"] == 3
    assert s["skills"][0] == {"name": "deploy", "uses": 1, "sessions": 1,
                              "last_used": "2026-07-01T09:05:00Z"}
    assert len(s["trend"]) == 4 and s["trend"][0]["hunting_ratio"] == 0.2
    assert s["notes"] == [{"ts": "2026-07-01T10:00:00Z", "text": "sharpened UX router"}]
    # three task clusters: UX (2 similar sessions merged via Jaccard), database, incident
    assert len(s["clusters"]) == 3, s["clusters"]
    assert s["clusters"][0]["count"] == 2 and s["clusters"][0]["variants"] == 2
    assert "docs/design/ui-patterns.md" in s["clusters"][0]["paths"]
    assert {"pair": ["docs/README.md", "docs/design/ui-patterns.md"], "count": 2} in s["co_read_top"]

    assert s["health"] == {"score": 51, "grade": "D", "coverage": 0.42,
                           "drivers": ["18 of 33 docs untouched",
                                       "11 router gaps (untouched and unreferenced)",
                                       "hunting ratio 0.12"]}

    # router-gap detection: accessibility.md is untouched AND unreferenced;
    # workflow.md is untouched but development/index.md mentions it
    detail = {d["path"]: d["referenced_from"] for d in s["untouched_detail"]}
    assert detail["docs/design/accessibility.md"] == []
    assert "docs/development/index.md" in detail["docs/development/workflow.md"]

    # folder heat/cold map: design 3/4 touched, security fully cold, runbooks 1/2
    folders = {f["folder"]: f for f in s["folders"]}
    assert folders["docs/design"]["touched"] == 3 and folders["docs/design"]["coverage"] == 0.75
    assert folders["docs/security"]["coverage"] == 0.0
    assert folders["docs/operations/runbooks"]["touched"] == 1
    assert folders["docs/README.md".rsplit("/", 1)[0]]["reads"] == 3  # docs/ root folder


def _bulk_events(reads, sessions, days):
    events = []
    for i in range(reads):
        day = 1 + (i * days) // reads
        session = f"S{i % sessions}"
        events.append({"t": "read", "ts": f"2026-07-{day:02d}T09:{i % 60:02d}:00Z",
                       "session": session, "tool": "Read", "path": "docs/a.md", "agent": "main"})
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
    write_history(tmp_path, [{"t": "read", "ts": "2026-07-01T09:00:00Z", "session": "A",
                              "tool": "Read", "path": "docs/ghost.md", "agent": "main"}])
    mod = load_script("tt-stats.py", tmp_path)
    explicit = str(tmp_path / ".trigger-tree" / "history.jsonl")
    s = run_stats(mod, monkeypatch, [explicit])
    assert s["unknown_reads"] == ["docs/ghost.md"]
    assert s["untouched"] == ["docs/a.md"]


def test_two_prompts_in_one_session_make_two_buckets(tmp_path, monkeypatch):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.md").write_text("x")
    (tmp_path / "docs" / "b.md").write_text("x")
    write_history(tmp_path, [
        {"t": "prompt", "ts": "2026-07-01T09:00:00Z", "session": "A", "prompt": "task one"},
        {"t": "read", "ts": "2026-07-01T09:00:10Z", "session": "A", "tool": "Read",
         "path": "docs/a.md", "agent": "main"},
        {"t": "prompt", "ts": "2026-07-01T09:05:00Z", "session": "A", "prompt": "task two"},
        {"t": "read", "ts": "2026-07-01T09:05:10Z", "session": "A", "tool": "Read",
         "path": "docs/b.md", "agent": "main"},
    ])
    mod = load_script("tt-stats.py", tmp_path)
    s = run_stats(mod, monkeypatch)
    assert s["totals"]["prompts_with_doc_reads"] == 2
    assert len(s["clusters"]) == 2  # disjoint sets don't cluster together


import os as _os
import pytest


@pytest.mark.skipif(_os.name == "nt", reason="chmod 0 does not block reads on Windows")
def test_unreadable_doc_does_not_break_crossref(tmp_path, monkeypatch):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.md").write_text("x")
    locked = tmp_path / "docs" / "locked.md"
    locked.write_text("secret")
    locked.chmod(0)
    try:
        write_history(tmp_path, [{"t": "read", "ts": "2026-07-01T09:00:00Z", "session": "A",
                                  "tool": "Read", "path": "docs/a.md", "agent": "main"}])
        mod = load_script("tt-stats.py", tmp_path)
        s = run_stats(mod, monkeypatch)
        assert "docs/locked.md" in s["untouched"]  # unreadable file still analyzed
    finally:
        locked.chmod(0o644)


def test_trend_skips_unparseable_timestamps(tmp_path, monkeypatch):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.md").write_text("x")
    write_history(tmp_path, [
        {"t": "read", "ts": "not-a-ts", "session": "A", "tool": "Read",
         "path": "docs/a.md", "agent": "main"},
        {"t": "read", "ts": "2026-07-01T09:00:00Z", "session": "A", "tool": "Read",
         "path": "docs/a.md", "agent": "main"},
    ])
    mod = load_script("tt-stats.py", tmp_path)
    s = run_stats(mod, monkeypatch)
    assert len(s["trend"]) == 1 and s["trend"][0]["reads"] == 1
