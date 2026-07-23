import importlib.util
import os

import pytest
from conftest import REPO

spec = importlib.util.spec_from_file_location(
    "release_notes", os.path.join(REPO, ".github", "scripts", "release_notes.py")
)
release_notes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release_notes)

CHANGELOG = """# Changelog

## 2.0.0 — 2026-08-01

- Second entry line.

## 1.9.9 — 2026-07-30

- First entry line.
- Another line.
"""


def test_extracts_exactly_the_requested_version_without_heading():
    body = release_notes.changelog_section(CHANGELOG, "1.9.9")
    assert body == "- First entry line.\n- Another line."
    assert "2.0.0" not in body


def test_release_body_appends_install_footer_once():
    body = release_notes.release_body("v2.0.0", CHANGELOG)
    assert body.startswith("- Second entry line.")
    assert body.count("/plugin install trigger-tree@trigger-tree") == 1
    # Codex pint op de eigen tag; `codex plugin install` bestaat niet (issue #12).
    assert "codex plugin marketplace add Hedde/trigger_tree --ref v2.0.0" in body
    assert "codex plugin add trigger-tree@trigger-tree" in body
    assert "codex plugin install" not in body


def test_unknown_and_empty_versions_fail_loudly():
    with pytest.raises(SystemExit):
        release_notes.changelog_section(CHANGELOG, "9.9.9")
    with pytest.raises(SystemExit):
        release_notes.changelog_section(
            "## 3.0.0 — 2026-01-01\n\n## 2.9.0 — 2025-12-01\n- x\n", "3.0.0"
        )


def test_release_body_matches_the_real_changelog_head():
    text = open(os.path.join(REPO, "CHANGELOG.md"), encoding="utf-8").read()
    import json

    manifest = json.load(
        open(os.path.join(REPO, ".claude-plugin", "plugin.json"), encoding="utf-8")
    )
    body = release_notes.release_body(f"v{manifest['version']}", text)
    assert body.strip()
