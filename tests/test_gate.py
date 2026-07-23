import json
import os
import stat
import subprocess
import sys

import pytest
from conftest import FIXTURE, REPO, load_script

STATS = {
    "router_coverage": [
        {
            "folder": "docs/ui",
            "router": "docs/ui/index.md",
            "files": 3,
            "listed": 2,
            "unlisted": ["docs/ui/_tpl.md", "docs/ui/gap.md"],
        }
    ],
    "untouched_detail": [
        {
            "path": "docs/ui/index.md",
            "inbound_refs": 1,
            "is_router": True,
            "router_mentions_target": True,
            "template": False,
        },
        {
            "path": "docs/ui/gap.md",
            "inbound_refs": 0,
            "is_router": False,
            "router_mentions_target": False,
            "template": False,
        },
        {
            "path": "docs/ui/linked.md",
            "inbound_refs": 2,
            "is_router": False,
            "router_mentions_target": True,
            "template": False,
        },
        {"path": "docs/ui/_tpl.md", "inbound_refs": 0, "template": True},
        {
            "path": "skills/x/SKILL.md",
            "inbound_refs": 0,
            "is_router": False,
            "router_mentions_target": False,
            "template": False,
        },
    ],
    "folders": [
        {"folder": "(root)", "files": 1, "has_index": True},
        {"folder": ".claude/rules", "files": 1, "has_index": False},
        {"folder": "docs/ui", "files": 3, "has_index": True},
        {"folder": "docs/ops", "files": 2, "has_index": False},
        {"folder": "skills/x", "files": 1, "has_index": False},
        {"folder": "docs/empty", "files": 0, "has_index": False},
    ],
}


def gate(tmp_path, monkeypatch, stats=STATS, watched=(1, 2)):
    mod = load_script("tt-gate.py", tmp_path)
    monkeypatch.setattr(mod, "ROOT", str(tmp_path))
    monkeypatch.setattr(mod, "structure_stats", lambda: json.loads(json.dumps(stats)))
    monkeypatch.setattr(
        mod,
        "scan_markdown",
        lambda *_args, **_kw: {
            "watched": watched[0],
            "markdown": watched[1],
            "paths": ["docs/ui/index.md", "LOOSE.md"][: watched[1]],
        },
    )
    return mod


def test_measure_scores_components_and_names_offenders(tmp_path, monkeypatch):
    mod = gate(tmp_path, monkeypatch)
    result = mod.measure(mod.structure_stats())
    assert result["unlisted"] == ["docs/ui/gap.md"]  # template filtered
    assert result["orphans"] == ["docs/ui/gap.md", "skills/x/SKILL.md"]
    assert result["folders_without_entry_point"] == ["docs/ops"]  # skill package skipped
    assert result["components"] == {
        "routed": 67,
        "linked": 50,
        "entry_points": 50,
        "watch_scope": 50,
    }
    assert result["score"] == 57
    assert result["unwatched"] == ["LOOSE.md"]
    assert mod._fraction(0, 0) == 1.0


def test_badge_colors_cover_the_full_ramp(tmp_path, monkeypatch):
    mod = gate(tmp_path, monkeypatch)
    ramp = {95: "brightgreen", 85: "green", 75: "yellow", 65: "orange", 10: "red"}
    for score, color in ramp.items():
        payload = mod.badge_payload(score)
        assert payload["color"] == color and payload["message"] == f"{score}%"
        assert payload["label"] == "docs discoverability"


def test_run_reports_hint_without_baseline_and_writes_badge(tmp_path, monkeypatch, capsys):
    mod = gate(tmp_path, monkeypatch)
    badge = tmp_path / "badge.json"
    assert mod.run(["--badge", str(badge)]) == 0
    out = capsys.readouterr().out
    assert "docs discoverability: 57%" in out
    assert "docs/ui/gap.md — add a link in the folder's entry point" in out
    assert "docs/ops — add README.md, _index.md, or index.md" in out
    assert "No baseline committed yet" in out and "gate passed" in out
    assert "Outside the watch scope (1):" in out and "LOOSE.md" in out
    assert json.loads(badge.read_text())["message"] == "57%"


def test_baseline_ratchet_fails_on_regression_and_updates(tmp_path, monkeypatch, capsys):
    mod = gate(tmp_path, monkeypatch)
    assert mod.run(["--update-baseline"]) == 0
    baseline = tmp_path / ".trigger-tree" / "gate.json"
    assert json.loads(baseline.read_text()) == {"schema": 1, "score": 57}
    assert mod.run([]) == 0  # equal score passes
    baseline.write_text(json.dumps({"schema": 1, "score": 90}))
    assert mod.run([]) == 1
    assert "regressed below the committed baseline 90" in capsys.readouterr().out
    assert mod.run(["--baseline", str(baseline)]) == 1  # absolute path branch


def test_min_score_gate_and_vacuous_empty_repo(tmp_path, monkeypatch, capsys):
    mod = gate(tmp_path, monkeypatch)
    assert mod.run(["--min-score", "80"]) == 1
    assert "below --min-score 80" in capsys.readouterr().out
    empty = {"router_coverage": [], "untouched_detail": [], "folders": []}
    mod2 = gate(tmp_path, monkeypatch, stats=empty, watched=(0, 0))
    assert mod2.run([]) == 0
    assert "nothing to gate" in capsys.readouterr().out


def test_step_summary_written_for_pass_fail_and_baseline_update(tmp_path, monkeypatch, capsys):
    mod = gate(tmp_path, monkeypatch)
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    assert mod.run([]) == 0
    text = summary.read_text(encoding="utf-8")
    assert "### 🌳 docs discoverability: 57%" in text
    assert "| watch scope | 50% |" in text
    assert "`docs/ui/gap.md` — add a link in the folder's entry point" in text
    assert "**✅ gate passed**" in text
    assert mod.run(["--update-baseline"]) == 0
    assert "**✅ baseline updated to 57**" in summary.read_text(encoding="utf-8")
    (tmp_path / ".trigger-tree" / "gate.json").write_text('{"schema": 1, "score": 90}')
    assert mod.run([]) == 1
    assert (
        "**❌ GATE FAILED: score 57 regressed below the committed baseline 90"
        in summary.read_text(encoding="utf-8")
    )
    capsys.readouterr()


def test_step_summary_caps_lists_and_skips_empty_sections(tmp_path, monkeypatch):
    mod = gate(tmp_path, monkeypatch)
    summary = tmp_path / "s.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    result = {
        "components": {"routed": 10},
        "unlisted": [],
        "orphans": [f"docs/{index}.md" for index in range(7)],
        "folders_without_entry_point": [],
        "unwatched": [],
    }
    mod._write_step_summary(result, 10, ["gate passed"])
    text = summary.read_text(encoding="utf-8")
    assert "Unlisted" not in text and "Outside the watch scope" not in text
    assert "… +2 more" in text


def test_step_summary_absent_without_ci_hook(tmp_path, monkeypatch):
    mod = gate(tmp_path, monkeypatch)
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    mod._write_step_summary(
        {
            "components": {},
            "unlisted": [],
            "orphans": [],
            "folders_without_entry_point": [],
            "unwatched": [],
        },
        100,
        ["x"],
    )
    assert not list(tmp_path.glob("*.md"))


def test_sarif_report_follows_the_standard_and_is_deterministic(tmp_path, monkeypatch):
    mod = gate(tmp_path, monkeypatch)
    sarif_path = tmp_path / "gate.sarif"
    assert mod.run(["--sarif", str(sarif_path)]) == 0
    first = sarif_path.read_bytes()
    report = json.loads(first)
    assert report["version"] == "2.1.0" and "sarif-2.1.0" in report["$schema"]
    run = report["runs"][0]
    assert run["tool"]["driver"]["name"] == "trigger-tree-gate"
    assert [rule["id"] for rule in run["tool"]["driver"]["rules"]] == [
        "TTD001",
        "TTD002",
        "TTD003",
        "TTD004",
    ]
    by_rule = {}
    for finding in run["results"]:
        by_rule.setdefault(finding["ruleId"], []).append(finding)
    assert by_rule["TTD001"][0]["locations"][0]["physicalLocation"]["artifactLocation"]["uri"] == (
        "docs/ui/gap.md"
    )
    assert by_rule["TTD001"][0]["level"] == "warning"
    assert by_rule["TTD004"][0]["level"] == "note"
    assert run["properties"]["verdict"] == "passed" and run["properties"]["score"] == 57
    assert mod.run(["--sarif", str(sarif_path)]) == 0
    assert sarif_path.read_bytes() == first  # byte-identiek: deterministisch


def test_sarif_verdicts_cover_failure_and_baseline_update(tmp_path, monkeypatch):
    mod = gate(tmp_path, monkeypatch)
    sarif_path = tmp_path / "gate.sarif"
    assert mod.run(["--update-baseline", "--sarif", str(sarif_path)]) == 0
    assert json.loads(sarif_path.read_text())["runs"][0]["properties"]["verdict"] == (
        "baseline-updated"
    )
    (tmp_path / ".trigger-tree" / "gate.json").write_text('{"schema": 1, "score": 90}')
    assert mod.run(["--sarif", str(sarif_path)]) == 1
    assert json.loads(sarif_path.read_text())["runs"][0]["properties"]["verdict"] == "failed"


def test_tool_version_comes_from_the_manifest_with_fallback(tmp_path, monkeypatch):
    mod = gate(tmp_path, monkeypatch)
    import json as json_module

    real = json_module.load(
        open(os.path.join(REPO, ".claude-plugin", "plugin.json"), encoding="utf-8")
    )["version"]
    assert mod._version() == real
    monkeypatch.setattr(mod, "SCRIPT_DIR", str(tmp_path / "nergens" / "scripts"))
    assert mod._version() == "unknown"


def test_offender_lists_are_capped(tmp_path, monkeypatch):
    mod = gate(tmp_path, monkeypatch)
    lines = mod._offenders("Orphans", [f"docs/{index}.md" for index in range(7)], "fix it")
    assert lines[0] == "Orphans (7):" and "… +2 more" in lines[-1]
    assert mod._offenders("Orphans", [], "fix it") == []


def test_baseline_validation_fails_loudly(tmp_path, monkeypatch, capsys):
    mod = gate(tmp_path, monkeypatch)
    bad = tmp_path / "bad.json"
    bad.write_text("not json")
    monkeypatch.setattr(sys, "argv", ["tt-gate.py", "--baseline", str(bad)])
    assert mod.main() == 2
    assert "not valid JSON" in capsys.readouterr().err
    bad.write_text(json.dumps({"schema": 99}))
    assert mod.main() == 2
    assert mod.load_baseline(str(tmp_path / "missing.json")) is None


def test_analysis_failure_exits_two(tmp_path, monkeypatch, capsys):
    mod = gate(tmp_path, monkeypatch)

    def boom():
        raise subprocess.CalledProcessError(1, ["tt-stats"], stderr="stats exploded")

    monkeypatch.setattr(mod, "structure_stats", boom)
    monkeypatch.setattr(sys, "argv", ["tt-gate.py"])
    assert mod.main() == 2
    assert "stats exploded" in capsys.readouterr().err


def test_refuse_unsafe_rejects_symlinks_via_portable_metadata(tmp_path, monkeypatch):
    """Cover the refusal branch on every platform, including runners without symlinks."""
    mod = gate(tmp_path, monkeypatch)
    victim = tmp_path / "victim.json"
    victim.write_text("{}")
    real_lstat = os.lstat

    class LinkStat:
        st_mode = stat.S_IFLNK | 0o777

    monkeypatch.setattr(
        mod.os, "lstat", lambda p: LinkStat() if str(p) == str(victim) else real_lstat(p)
    )
    with pytest.raises(RuntimeError, match="symlinked"):
        mod.write_json(str(victim), {})


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission semantics")
def test_write_json_refuses_symlinked_destination(tmp_path, monkeypatch):
    mod = gate(tmp_path, monkeypatch)
    target = tmp_path / "elsewhere.json"
    target.write_text("{}")
    link = tmp_path / "link.json"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("symlinks unavailable")
    with pytest.raises(RuntimeError, match="symlinked"):
        mod.write_json(str(link), {})


def test_write_json_cleans_up_when_serialization_fails(tmp_path, monkeypatch):
    mod = gate(tmp_path, monkeypatch)
    with pytest.raises(TypeError):
        mod.write_json(str(tmp_path / "x.json"), {"bad": object()})
    assert not (tmp_path / "x.json").exists()
    assert not [name for name in os.listdir(tmp_path) if name.startswith(".gate.")]


def test_watch_regex_prefers_project_override_and_survives_missing_files(tmp_path, monkeypatch):
    mod = load_script("tt-gate.py", tmp_path)
    monkeypatch.setattr(mod, "ROOT", str(tmp_path))
    assert mod.watch_regex() != "(?!)"  # plugin fallback config found
    (tmp_path / ".trigger-tree").mkdir()
    (tmp_path / ".trigger-tree" / "config.sh").write_text("TT_WATCH_REGEX='^only/.*$'\n")
    assert mod.watch_regex() == "^only/.*$"
    monkeypatch.setattr(mod, "SCRIPT_DIR", str(tmp_path / "nowhere"))
    (tmp_path / ".trigger-tree" / "config.sh").unlink()
    assert mod.watch_regex() == "(?!)"


def test_structure_stats_runs_the_real_analysis_without_telemetry(monkeypatch):
    mod = load_script("tt-gate.py", FIXTURE)
    stats = mod.structure_stats()
    assert stats["totals"]["reads"] == 0  # telemetry ignored by design
    assert stats["router_coverage"]


def test_scope_ignore_acknowledges_files_but_never_watched_ones(tmp_path, monkeypatch):
    mod = load_script("tt-gate.py", tmp_path)
    monkeypatch.setattr(mod, "ROOT", str(tmp_path))
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "kept.md").write_text("doc")
    (tmp_path / "CHANGELOG.md").write_text("log")
    (tmp_path / "NOTES.md").write_text("notes")
    (tmp_path / ".trigger-tree").mkdir()
    (tmp_path / ".trigger-tree" / "config.sh").write_text(
        "TT_WATCH_REGEX='^docs/.*$'\nTT_SCOPE_IGNORE='CHANGELOG.md,docs/*'\n"
    )
    assert mod.scope_ignore() == ("CHANGELOG.md", "docs/*")
    scope = mod.scan_markdown(str(tmp_path), "^docs/.*$", ignore_globs=mod.scope_ignore())
    # CHANGELOG erkend en weg; docs/kept.md matcht de watch-regex en blijft dus staan
    assert scope["markdown"] == 2 and scope["watched"] == 1
    assert sorted(scope["paths"]) == ["NOTES.md", "docs/kept.md"]
    assert mod._conf_value("TT_ONBEKEND") == ""


def test_scope_ignore_falls_back_to_plugin_default(tmp_path, monkeypatch):
    mod = load_script("tt-gate.py", tmp_path)
    monkeypatch.setattr(mod, "ROOT", str(tmp_path))
    assert mod.scope_ignore() == ()  # plugin default is leeg
