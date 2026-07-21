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


def test_prioritized_suggestions_are_bounded_and_actionable(monkeypatch):
    mod = load_script("tt-suggestions.py", ".")
    stats = base_stats()
    stats["review_candidates"] = [
        {
            "path": "docs/ui/empty.md",
            "referenced_from": [],
            "template": False,
            "classification": "review_candidate",
            "why": ["no reads"],
            "router": "docs/ui/_index.md",
            "router_mentions_target": False,
            "caveat": "Low reads can mean rare-but-critical; verify before archiving.",
        },
        {
            "path": "docs/_template.md",
            "referenced_from": [],
            "template": True,
            "classification": "protected",
            "why": ["template or intentional archive"],
            "caveat": "Low reads can mean rare-but-critical; verify before archiving.",
        },
    ]
    stats["folders"] = [
        {"folder": "(root)", "files": 2, "touched": 0, "coverage": 0, "has_index": True},
        {"folder": ".claude/rules", "files": 2, "touched": 0, "coverage": 0, "has_index": False},
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
    stats["unknown_reads"] = ["docs/gone.md"]
    out = run_main(mod, monkeypatch, stats)
    assert "changes nothing until you confirm" in out
    assert "1. Review candidate: add a link to docs/ui/empty.md" in out
    assert "Review, likely keep — rare-but-critical: docs/_template.md" in out
    assert "Review routing for docs/ops/" in out
    assert "search telemetry is correlational" in out
    assert ".claude/rules" not in out
    assert out.count("\n") == 7  # heading + five suggestions + confirmation


def test_safety_rule_is_never_a_prune_candidate(monkeypatch):
    mod = load_script("tt-suggestions.py", ".")
    stats = base_stats()
    stats["review_candidates"] = [
        {
            "path": ".claude/rules/security.md",
            "classification": "protected",
            "why": ["safety path"],
            "caveat": "Low reads can mean rare-but-critical; verify purpose and owners before archiving.",
        }
    ]
    out = run_main(mod, monkeypatch, stats)
    assert "Review, likely keep — rare-but-critical" in out
    assert "safety path" in out
    assert "prune" not in out.lower() and "safe to remove" not in out.lower()


def test_pre_1_0_stats_payload_gets_safe_review_language():
    mod = load_script("tt-suggestions.py", ".")
    stats = base_stats()
    stats.pop("review_candidates")
    stats["untouched_detail"] = [
        {"path": "docs/legacy.md", "referenced_from": [], "template": False},
        {"path": "docs/referenced.md", "referenced_from": ["docs/index.md"], "template": False},
    ]
    suggestions = mod.build_suggestions(stats)
    assert len(suggestions) == 1
    assert suggestions[0].startswith("Review routing")
    assert "rare-but-critical" in suggestions[0]


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
    assert mod.build_suggestions(stats) == []


def test_verified_unlisted_file_creates_one_existing_router_proposal():
    mod = load_script("tt-suggestions.py", ".")
    stats = base_stats()
    stats["router_coverage"] = [
        {
            "folder": "docs/ui",
            "router": "docs/ui/_index.md",
            "files": 2,
            "listed": 1,
            "unlisted": ["docs/ui/missing.md"],
        }
    ]
    assert mod.build_suggestions(stats) == [
        "Review candidate: add a link to docs/ui/missing.md in docs/ui/_index.md — "
        "both files exist and the folder router does not mention the target."
    ]


def test_no_suggestions_has_no_confirmation_prompt(monkeypatch):
    mod = load_script("tt-suggestions.py", ".")
    out = run_main(mod, monkeypatch, base_stats())
    assert "No evidence-backed" in out and "Reply with" not in out
