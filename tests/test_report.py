import os
import sys

from conftest import FIXTURE, load_script


def run_report(mod, monkeypatch, capsys, project):
    # main() shells out to tt-stats.py, which reads CLAUDE_PROJECT_DIR from the
    # real environment — pin it so the subprocess sees the same project.
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project))
    monkeypatch.setattr(sys, "argv", ["tt-report.py"])
    mod.main()
    return capsys.readouterr().out.strip()


def test_heat_color_and_escape():
    mod = load_script("tt-report.py", FIXTURE)
    assert mod.heat_color(0, 10) == mod.HEAT[0]
    assert mod.heat_color(10, 10) == mod.HEAT[-1]
    assert mod.esc(None) == "—"
    assert mod.esc("<b>") == "&lt;b&gt;"


def test_full_report_on_fixture(monkeypatch, capsys):
    mod = load_script("tt-report.py", FIXTURE)
    out_path = run_report(mod, monkeypatch, capsys, FIXTURE)
    html = open(out_path, encoding="utf-8").read()
    for expected in (
        "<title>trigger-tree Report</title>",
        "Most consulted",
        "Skill usage",
        "Review candidates (untouched paths)",
        "Folder heat",
        "router gap",
        "referenced from",
        "Trend",
        "sharpened UX router",
        "Task clusters",
        "Most often read together",
        "cold-start",
        "Documentation health",
        "provisional",
        "no index file",
        "template — intentional archive",
    ):
        assert expected in html, expected
    os.remove(out_path)  # keep the fixture clean for other tests


def test_report_on_empty_project(tmp_path, monkeypatch, capsys):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.md").write_text("x")
    mod = load_script("tt-report.py", tmp_path)
    out_path = run_report(mod, monkeypatch, capsys, tmp_path)
    html = open(out_path, encoding="utf-8").read()
    assert "Measurement just started" in html
    assert "docs/a.md" in html  # untouched listing
    assert "not a removal recommendation" in html


def test_report_when_nothing_untouched(tmp_path, monkeypatch, capsys):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.md").write_text("x")
    (tmp_path / ".trigger-tree").mkdir()
    (tmp_path / ".trigger-tree" / "history.jsonl").write_text(
        '{"t":"read","ts":"2026-07-01T09:00:00Z","session":"A","tool":"Read",'
        '"path":"docs/a.md","agent":"main"}\n'
    )
    mod = load_script("tt-report.py", tmp_path)
    html = open(run_report(mod, monkeypatch, capsys, tmp_path), encoding="utf-8").read()
    assert "None — every inventoried file has been read" in html


def test_experimental_outcome_view_renders_with_causal_warning(tmp_path, monkeypatch, capsys):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.md").write_text("x")
    telemetry = tmp_path / ".trigger-tree"
    telemetry.mkdir()
    (telemetry / "config.sh").write_text("TT_EXPERIMENTAL_OUTCOMES='on'\n")
    (telemetry / "history.jsonl").write_text(
        '{"t":"read","session":"S","path":"docs/a.md"}\n'
        '{"t":"outcome","session":"S","git_commit_landed":true}\n'
    )
    mod = load_script("tt-report.py", tmp_path)
    html = open(run_report(mod, monkeypatch, capsys, tmp_path), encoding="utf-8").read()
    assert "Experimental outcome correlation" in html
    assert "experimental correlation — not causal" in html
    assert "does not show that reading a document caused an outcome" in html
