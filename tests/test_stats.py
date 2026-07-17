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
    assert mod.jaccard([], []) == 0.0
    assert mod.jaccard(["a", "b"], ["a", "c"]) == 1 / 3
    assert mod.fingerprint(["b", "a"]) == mod.fingerprint(["a", "b"])


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
    assert s["totals"]["reads"] == 4 and s["totals"]["scans"] == 1 and s["totals"]["skill_uses"] == 1
    assert s["untouched"] == ["agents/x.md"]
    assert s["always_loaded"] == ["CLAUDE.md"]  # invoked skill's SKILL.md excluded
    assert s["skills"][0] == {"name": "deploy", "uses": 1, "sessions": 1,
                              "last_used": "2026-07-01T09:00:20Z"}
    assert len(s["trend"]) == 2 and s["trend"][0]["hunting_ratio"] == 0.5
    assert s["notes"] == [{"ts": "2026-07-01T10:00:00Z", "text": "sharpened UX router"}]
    assert len(s["clusters"]) == 1
    assert s["clusters"][0]["count"] == 2 and s["clusters"][0]["variants"] == 2
    assert {"pair": ["docs/a.md", "docs/sub/b.md"], "count": 2} in s["co_read_top"]


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
