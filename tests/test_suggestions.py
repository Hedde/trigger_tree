import io
import json
import subprocess
import sys

from conftest import load_script


def base_stats(maturity="mature"):
    return {
        "maturity": maturity,
        "sessions": 8,
        "totals": {"reads": 120, "scans": 14},
        "untouched_detail": [],
        "review_candidates": [],
        "folders": [],
        "hunting": [],
        "unknown_reads": [],
    }


def gap_candidate(path="docs/ui/empty.md", router="docs/ui/_index.md", inbound=0):
    return {
        "path": path,
        "referenced_from": [],
        "inbound_refs": inbound,
        "template": False,
        "classification": "review_candidate",
        "why": ["no reads"],
        "router": router,
        "router_mentions_target": False,
        "caveat": "Low reads can mean rare-but-critical; verify before archiving.",
    }


def protected_candidate(path, why=("safety path",)):
    return {
        "path": path,
        "classification": "protected",
        "why": list(why),
        "caveat": "Low reads can mean rare-but-critical; verify purpose and owners before archiving.",
    }


def run_main(mod, monkeypatch, stats):
    completed = subprocess.CompletedProcess([], 0, json.dumps(stats), "")
    monkeypatch.setattr(mod.subprocess, "run", lambda *_args, **_kwargs: completed)
    out = io.StringIO()
    monkeypatch.setattr(sys, "stdout", out)
    mod.main()
    return out.getvalue()


def test_router_target():
    mod = load_script("tt-suggestions.py", ".")
    coverage = [
        {"folder": "(root)", "router": "CLAUDE.md"},
        {"folder": "docs", "router": "docs/README.md"},
        {"folder": "docs/ui", "router": "docs/ui/_index.md"},
    ]
    assert mod.router_for("docs/a.md", coverage) == "docs/README.md"
    assert mod.router_for("docs/ui/a.md", coverage) == "docs/ui/_index.md"
    assert mod.router_for("root.md", coverage) == "CLAUDE.md"
    assert mod.router_for("docs/missing/a.md", coverage) is None


def test_cold_start_is_one_concise_line(monkeypatch):
    mod = load_script("tt-suggestions.py", ".")
    out = run_main(mod, monkeypatch, base_stats("cold-start"))
    assert out.count("\n") == 1 and "120 reads, 8 sessions" in out


def test_protected_files_never_crowd_out_appliable_edits(monkeypatch):
    """Regression: many safety-path files must not fill the numbered slots."""
    mod = load_script("tt-suggestions.py", ".")
    stats = base_stats()
    stats["review_candidates"] = [
        protected_candidate(f".claude/rules/rule-{index}.md") for index in range(6)
    ] + [gap_candidate()]
    stats["folders"] = [
        {"folder": "docs/empty", "files": 0, "touched": 0, "coverage": 0, "has_index": False},
        {"folder": "docs/ui", "files": 8, "touched": 2, "coverage": 0.25, "has_index": False},
        {"folder": "docs/ops", "files": 3, "touched": 0, "coverage": 0, "has_index": True},
    ]
    stats["hunting"] = [
        {
            "path": "docs/ui",
            "scans": 9,
            "sessions": 6,
            "total_sessions": 8,
            "tools": {"Bash": 9},
            "pattern": "distributed",
        }
    ]
    out = run_main(mod, monkeypatch, stats)
    assert "1. Add a link to docs/ui/empty.md in docs/ui/_index.md" in out
    assert "0 other docs link to it" in out
    assert "2. Add a folder entry point in docs/ui/" in out
    assert "Worth a look: docs/ui — 9 searches recur across 6/8 sessions (Bash ×9)" in out
    assert "Worth a look: docs/ops/ — none of its 3 files were read." in out
    assert "6 low-read files look rare-but-critical (safety path)" in out
    assert "Review, likely keep" not in out
    assert "docs/empty" not in out
    assert out.strip().endswith("Apply any of these? Reply with the numbers.")


def test_zero_edits_shows_summary_without_apply_prompt(monkeypatch):
    mod = load_script("tt-suggestions.py", ".")
    stats = base_stats()
    stats["review_candidates"] = [
        protected_candidate(".claude/rules/security.md"),
        protected_candidate("docs/incident-runbook.md", why=["referenced by 4 other docs"]),
    ]
    out = run_main(mod, monkeypatch, stats)
    assert "No evidence-backed router edits found." in out
    assert "2 low-read files look rare-but-critical" in out
    assert "referenced by 4 other docs; safety path" in out
    assert "Reply with" not in out and "1. " not in out
    assert "prune" not in out.lower() and "safe to remove" not in out.lower()


def test_edit_overflow_is_counted_not_dropped_silently(monkeypatch):
    mod = load_script("tt-suggestions.py", ".")
    stats = base_stats()
    stats["review_candidates"] = [
        gap_candidate(f"docs/ui/page-{index}.md", inbound=1) for index in range(7)
    ]
    tiers = mod.build_suggestions(stats)
    assert len(tiers["edits"]) == 5
    assert tiers["extra_edits"] == 2
    assert "1 other doc link to it" in tiers["edits"][0]
    assert mod._tools_label("Bash x3") == "Bash x3"
    out = run_main(mod, monkeypatch, stats)
    assert "+2 more — see /tt insights" in out


def test_unlisted_branch_skips_templates_and_duplicates():
    mod = load_script("tt-suggestions.py", ".")
    stats = base_stats()
    stats["review_candidates"] = [gap_candidate("docs/ui/x.md")]
    stats["router_coverage"] = [
        {
            "folder": "docs/ui",
            "router": "docs/ui/_index.md",
            "files": 3,
            "listed": 1,
            "unlisted": ["docs/ui/_snippet.md", "docs/ui/x.md", "docs/ui/y.md"],
        }
    ]
    tiers = mod.build_suggestions(stats)
    assert len(tiers["edits"]) == 2
    assert tiers["edits"][0].startswith("Add a link to docs/ui/x.md")
    assert tiers["edits"][1] == (
        "Add a link to docs/ui/y.md in docs/ui/_index.md — both files exist and the "
        "folder router does not mention the target (1/3 members listed)."
    )


def test_warming_marks_telemetry_observations_as_early_signal():
    mod = load_script("tt-suggestions.py", ".")
    stats = base_stats("warming")
    stats["folders"] = [
        {"folder": "docs/ops", "files": 3, "touched": 0, "coverage": 0, "has_index": True}
    ]
    stats["hunting"] = [
        {
            "path": "docs/ui",
            "scans": 9,
            "sessions": 6,
            "total_sessions": 8,
            "tools": {"Bash": 9},
            "pattern": "distributed",
        }
    ]
    tiers = mod.build_suggestions(stats)
    assert all(line.endswith("(early signal)") for line in tiers["observations"])
    mature = mod.build_suggestions({**stats, "maturity": "mature"})
    assert not any("early signal" in line for line in mature["observations"])


def test_pre_1_0_stats_payload_gets_safe_review_language():
    mod = load_script("tt-suggestions.py", ".")
    stats = base_stats()
    stats.pop("review_candidates")
    stats["untouched_detail"] = [
        {"path": "docs/legacy.md", "referenced_from": [], "template": False},
        {"path": "docs/referenced.md", "referenced_from": ["docs/index.md"], "template": False},
    ]
    tiers = mod.build_suggestions(stats)
    assert tiers["edits"] == []
    assert len(tiers["observations"]) == 1
    assert tiers["observations"][0].startswith("Worth a look: docs/legacy.md")
    assert "rare-but-critical" in tiers["observations"][0]


def test_existing_router_link_and_concentrated_search_do_not_create_proposals():
    mod = load_script("tt-suggestions.py", ".")
    stats = base_stats()
    stats["review_candidates"] = [
        {
            "path": "docs/ui/existing.md",
            "template": False,
            "classification": "review_candidate",
            "router": "docs/ui/_index.md",
            "router_mentions_target": True,
            "caveat": "Verify first.",
        }
    ]
    stats["router_coverage"] = [
        {
            "folder": "docs/ui",
            "router": "docs/ui/_index.md",
            "files": 1,
            "listed": 1,
            "unlisted": [],
        }
    ]
    stats["hunting"] = [
        {
            "path": "docs/ui",
            "scans": 40,
            "sessions": 2,
            "total_sessions": 20,
            "tools": {"Bash": 40},
            "pattern": "concentrated",
        }
    ]
    tiers = mod.build_suggestions(stats)
    assert tiers["edits"] == [] and tiers["observations"] == []
    assert tiers["protected_summary"] is None


def test_unknown_reads_surface_as_inventory_observations():
    mod = load_script("tt-suggestions.py", ".")
    stats = base_stats()
    stats["unknown_reads"] = ["docs/gone.md"]
    tiers = mod.build_suggestions(stats)
    assert tiers["observations"] == [
        "Worth a look: docs/gone.md — the file exists and was read, but is outside the "
        "current documentation inventory."
    ]


def test_no_suggestions_has_no_confirmation_prompt(monkeypatch):
    mod = load_script("tt-suggestions.py", ".")
    out = run_main(mod, monkeypatch, base_stats())
    assert "No evidence-backed" in out and "Reply with" not in out
