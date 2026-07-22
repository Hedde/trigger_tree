import json
import os
import stat
import sys
from types import SimpleNamespace

import pytest
from conftest import FIXTURE, load_script


def run_report(mod, monkeypatch, capsys, project):
    # main() shells out to tt-stats.py, which reads CLAUDE_PROJECT_DIR from the
    # real environment — pin it so the subprocess sees the same project.
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project))
    monkeypatch.setattr(sys, "argv", ["tt-report.py"])
    mod.main()
    return capsys.readouterr().out.strip()


def test_heat_color_and_escape(monkeypatch):
    mod = load_script("tt-report.py", FIXTURE)
    assert mod.heat_color(0, 10) == mod.HEAT[0]
    assert mod.heat_color(10, 10) == mod.HEAT[-1]
    assert mod.esc(None) == "—"
    assert mod.esc("<b>") == "&lt;b&gt;"
    assert mod.plugin_version() == "1.10.0"
    monkeypatch.setattr(mod, "SCRIPT_DIR", "/missing")
    assert mod.plugin_version() == "unknown"
    assert mod._points([], 10, 10) == []
    assert mod.sparkline_svg([1, 2], "short") == ""
    spark = mod.sparkline_svg([4, 4, 4], "all equal")
    assert "<svg" in spark and "all equal" in spark and ">4</text>" in spark
    assert mod.line_chart_svg([{"reads": 1}], (("reads", "reads", "red"),), "one") == ""
    trend = [
        {"period": "2026-07-01", "reads": 1, "small_n": True},
        {"period": "2026-07-02", "reads": 1000, "small_n": False},
        {"period": "2026-07-03", "reads": 2, "small_n": False},
    ]
    chart = mod.line_chart_svg(
        trend,
        (("reads", "reads", "red"),),
        "outlier",
        [{"ts": "2026-07-02T00:00:00Z", "text": "router edit"}],
    )
    assert "stroke-dasharray" in chart and "router edit" in chart and "reads 2" in chart
    assert mod.tree_svg([], "warming", 5).startswith("<svg")
    assert mod.tree_svg([], "cold-start", 5) == ""
    assert mod.tree_svg([], "warming", 4) == ""
    tree = mod.tree_svg(
        [
            {"path": "docs/a/" + "long-" * 20 + ".md", "heat": 8, "reads": 3},
            {"path": "docs/a/quiet.md", "heat": 0, "reads": 0},
            {"path": "docs/retired.md", "state": "retired", "heat": 99, "reads": 99},
        ],
        "warming",
        5,
    )
    assert "untouched" in tree and "…" in tree and "retired" not in tree
    large_tree = mod.tree_svg(
        [
            {"path": f"docs/reference/{index:03d}.md", "heat": index + 1, "reads": 1}
            for index in range(105)
        ],
        "mature",
        105,
    )
    assert large_tree.count("<g>") == 106  # one folder row plus every active file


def test_mature_report_renders_visuals_and_keeps_tables(tmp_path, monkeypatch, capsys):
    docs = tmp_path / "docs"
    docs.mkdir()
    for index in range(5):
        (docs / f"{index}.md").write_text("x")
    events = []
    for index in range(100):
        day = min(8, 1 + index // 13)
        events.append(
            json.dumps(
                {
                    "t": "read",
                    "ts": f"2026-07-{day:02d}T09:00:00Z",
                    "session": f"S{index % 4}",
                    "path": f"docs/{index % 5}.md",
                }
            )
        )
    telemetry = tmp_path / ".trigger-tree"
    telemetry.mkdir()
    (telemetry / "history.jsonl").write_text("\n".join(events) + "\n")
    mod = load_script("tt-report.py", tmp_path)
    rendered = open(run_report(mod, monkeypatch, capsys, tmp_path), encoding="utf-8").read()
    assert "class=tree-chart" in rendered
    assert "class=spark" in rendered and "class=chart" in rendered
    assert "<table>" in rendered and "docs/0.md" in rendered


def test_full_report_on_fixture(monkeypatch, capsys):
    mod = load_script("tt-report.py", FIXTURE)
    out_path = run_report(mod, monkeypatch, capsys, FIXTURE)
    html = open(out_path, encoding="utf-8").read()
    for expected in (
        "<title>trigger-tree Report</title>",
        "<meta charset=utf-8>",
        "Current heat",
        "30-day half-life",
        "Lifetime",
        "Skill usage",
        "Untouched review",
        "Folder heat",
        "router gap",
        "Inbound refs",
        "Trend",
        "sharpened UX router",
        "Task clusters",
        "Most often read together",
        "cold-start",
        "Documentation health",
        "a rule that is never read protects nothing",
        "class='note grade'",
        "provisional",
        "no index file",
        "Unread routers",
        "Folder-router coverage",
        "Search activity inside doc folders",
        "not its cause",
        "class=toc",
        "id=heat",
        "100% local — this file was generated on your machine and never uploaded",
        "trigger-tree 1.10.0",
    ):
        assert expected in html, expected
    assert html.index("id=search") < html.index("id=tasks") < html.index("id=routing")
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
    assert "--cold:#4775d1" in html and "--hot:#e53935" in html
    assert "class=tree-chart" not in html and "class=chart" not in html
    if os.name != "nt":
        assert stat.S_IMODE(os.stat(out_path).st_mode) == 0o600


@pytest.mark.skipif(os.name == "nt", reason="symlink creation needs elevated rights on Windows")
def test_report_replaces_symlink_without_touching_victim(tmp_path, monkeypatch, capsys):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.md").write_text("x")
    telemetry = tmp_path / ".trigger-tree"
    telemetry.mkdir()
    victim = tmp_path / "victim"
    victim.write_text("untouched\n")
    (telemetry / "report.html").symlink_to(victim)

    mod = load_script("tt-report.py", tmp_path)
    out_path = run_report(mod, monkeypatch, capsys, tmp_path)

    assert victim.read_text() == "untouched\n"
    assert not os.path.islink(out_path)
    assert "<title>trigger-tree Report</title>" in open(out_path, encoding="utf-8").read()


@pytest.mark.skipif(os.name == "nt", reason="symlink creation needs elevated rights on Windows")
def test_report_refuses_symlinked_telemetry_directory(tmp_path, monkeypatch, capsys):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.md").write_text("x")
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / ".trigger-tree").symlink_to(outside)
    mod = load_script("tt-report.py", tmp_path)

    with pytest.raises(RuntimeError, match="symlinked .trigger-tree"):
        run_report(mod, monkeypatch, capsys, tmp_path)
    assert not (outside / "report.html").exists()


def test_report_refuses_mocked_symlink_directory_on_every_platform(tmp_path, monkeypatch):
    mod = load_script("tt-report.py", tmp_path)
    out_dir = str(tmp_path / ".trigger-tree")
    monkeypatch.setattr(mod.os.path, "lexists", lambda path: os.fspath(path) == out_dir)
    monkeypatch.setattr(mod.os, "lstat", lambda _path: SimpleNamespace(st_mode=stat.S_IFLNK))

    with pytest.raises(RuntimeError, match="symlinked .trigger-tree"):
        mod.write_report("private")


def test_privacy_policy_matches_local_content_analysis():
    repo = os.path.dirname(os.path.dirname(__file__))
    privacy = open(os.path.join(repo, "PRIVACY.md"), encoding="utf-8").read()
    assert "Telemetry hooks store paths and event metadata" in privacy
    assert "Local analysis commands read selected documentation and instruction content" in privacy
    assert "never copied into\n  telemetry or uploaded" in privacy
    assert "No reading of file *contents*" not in privacy


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


def test_report_reconciles_inventory_separates_retired_and_hides_wide_windows(
    tmp_path, monkeypatch, capsys
):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "current.md").write_text("current")
    (tmp_path / "CLAUDE.md").write_text("always loaded")
    (tmp_path / ".trigger-tree").mkdir()
    (tmp_path / ".trigger-tree" / "history.jsonl").write_text(
        '{"t":"read","ts":"2026-07-20T09:00:00Z","session":"A",'
        '"path":"docs/current.md","agent":"main"}\n'
        '{"t":"read","ts":"2026-07-21T09:00:00Z","session":"A",'
        '"path":"docs/retired.md","agent":"feature"}\n'
    )

    mod = load_script("tt-report.py", tmp_path)
    html = open(run_report(mod, monkeypatch, capsys, tmp_path), encoding="utf-8").read()

    assert "1 touched + 0 untouched = 1" in html
    assert "1 evaluable + 1 always loaded" in html
    assert "Retired paths" in html and "docs/retired.md" in html
    current_table = html.split("<h2 id=heat>Current heat</h2>", 1)[1].split("</table>", 1)[0]
    assert "docs/retired.md" not in current_table
    assert "<th>7d</th>" not in html and "<th>30d</th>" not in html
    assert "main 1 · sub 0" in current_table


def test_report_folds_large_review_queue_and_emits_caveat_once(tmp_path, monkeypatch, capsys):
    (tmp_path / "docs").mkdir()
    for index in range(25):
        (tmp_path / "docs" / f"{index:02}.md").write_text("x")

    mod = load_script("tt-report.py", tmp_path)
    html = open(run_report(mod, monkeypatch, capsys, tmp_path), encoding="utf-8").read()

    assert "<summary>and 5 more</summary>" in html
    assert html.count("Low reads can mean rare-but-critical") == 1


def test_report_discloses_bounded_co_read_analysis(tmp_path, monkeypatch, capsys):
    (tmp_path / "docs").mkdir()
    events = ['{"t":"prompt","session":"S","prompt":"Review all docs"}']
    for index in range(201):
        path = f"docs/{index}.md"
        (tmp_path / path).write_text("x")
        events.append(json.dumps({"t": "read", "session": "S", "path": path}))
    telemetry = tmp_path / ".trigger-tree"
    telemetry.mkdir()
    (telemetry / "history.jsonl").write_text("\n".join(events) + "\n")

    mod = load_script("tt-report.py", tmp_path)
    html = open(run_report(mod, monkeypatch, capsys, tmp_path), encoding="utf-8").read()

    assert "Co-read pairs skipped for 1 oversized prompt" in html
    assert "task clusters and read counts remain complete" in html


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
