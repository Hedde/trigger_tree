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
    assert mod.router_for("docs/a.md") == "docs/README.md"
    assert mod.router_for("docs/ui/a.md") == "docs/ui/index.md"
    assert mod.router_for("root.md") == "docs/README.md"


def test_cold_start_is_one_concise_line(monkeypatch):
    mod = load_script("tt-suggestions.py", ".")
    out = run_main(mod, monkeypatch, base_stats("cold-start"))
    assert out.count("\n") == 1 and "120 reads, 8 sessions" in out


def test_prioritized_suggestions_are_bounded_and_actionable(monkeypatch):
    mod = load_script("tt-suggestions.py", ".")
    stats = base_stats()
    stats["untouched_detail"] = [
        {"path": "docs/ui/empty.md", "referenced_from": [], "template": False},
        {"path": "docs/_template.md", "referenced_from": [], "template": True},
    ]
    stats["folders"] = [
        {"folder": "(root)", "files": 2, "touched": 0, "coverage": 0, "has_index": True},
        {"folder": ".claude/rules", "files": 2, "touched": 0, "coverage": 0, "has_index": False},
        {"folder": "docs/ui", "files": 8, "touched": 2, "coverage": 0.25, "has_index": False},
        {"folder": "docs/ops", "files": 3, "touched": 0, "coverage": 0, "has_index": True},
    ]
    stats["hunting"] = [{"path": "docs/ui", "scans": 9}]
    stats["unknown_reads"] = ["docs/gone.md"]
    out = run_main(mod, monkeypatch, stats)
    assert "changes nothing until you confirm" in out
    assert "1. Add a link to docs/ui/empty.md" in out
    assert "2. Add docs/ui/index.md" in out
    assert "Route to or archive docs/ops/" in out
    assert "Sharpen the index instructions" in out
    assert "Fix the router reference" in out
    assert "_template" not in out and ".claude/rules" not in out
    assert out.count("\n") == 7  # heading + five suggestions + confirmation


def test_no_suggestions_has_no_confirmation_prompt(monkeypatch):
    mod = load_script("tt-suggestions.py", ".")
    out = run_main(mod, monkeypatch, base_stats())
    assert "No evidence-backed" in out and "Reply with" not in out
