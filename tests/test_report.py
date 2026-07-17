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
    html = open(out_path).read()
    for expected in ("<title>Trigger Tree Report</title>", "Most consulted", "Skill usage",
                     "Untouched paths", "Trend", "sharpened UX router", "Task clusters",
                     "Most often read together", "cold-start"):
        assert expected in html, expected
    os.remove(out_path)  # keep the fixture clean for other tests


def test_report_on_empty_project(tmp_path, monkeypatch, capsys):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.md").write_text("x")
    mod = load_script("tt-report.py", tmp_path)
    out_path = run_report(mod, monkeypatch, capsys, tmp_path)
    html = open(out_path).read()
    assert "Measurement just started" in html
    assert "docs/a.md" in html  # untouched listing
