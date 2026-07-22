import importlib.util
import json
from pathlib import Path

import pytest
from conftest import REPO


def load_release_integrity():
    path = Path(REPO) / ".github" / "scripts" / "release_integrity.py"
    spec = importlib.util.spec_from_file_location("release_integrity_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_release(root, version="1.0.0-rc.1"):
    plugin_dir = root / ".claude-plugin"
    plugin_dir.mkdir()
    (plugin_dir / "plugin.json").write_text(
        json.dumps({"name": "trigger-tree", "version": version}), encoding="utf-8"
    )
    (plugin_dir / "marketplace.json").write_text(
        json.dumps(
            {
                "name": "trigger-tree",
                "plugins": [{"name": "trigger-tree", "version": version}],
            }
        ),
        encoding="utf-8",
    )
    codex_dir = root / ".codex-plugin"
    codex_dir.mkdir()
    (codex_dir / "plugin.json").write_text(
        json.dumps({"name": "trigger-tree", "version": version}), encoding="utf-8"
    )
    (root / "CHANGELOG.md").write_text(f"## {version} — 2026-07-19\n", encoding="utf-8")
    (root / "pyproject.toml").write_text(
        f'[project]\nname = "trigger-tree"\nversion = "{version}"\n', encoding="utf-8"
    )


def test_release_integrity_accepts_semver_release_candidate(tmp_path, monkeypatch, capsys):
    mod = load_release_integrity()
    write_release(tmp_path)
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setattr(mod, "check_docs_currency", lambda _root: None)
    mod.main("v1.0.0-rc.1")
    assert "consistently describes v1.0.0-rc.1" in capsys.readouterr().out


def test_release_integrity_rejects_bad_or_inconsistent_metadata(tmp_path, monkeypatch):
    mod = load_release_integrity()
    write_release(tmp_path)
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setattr(mod, "check_docs_currency", lambda _root: None)
    with pytest.raises(SystemExit, match="not vMAJOR"):
        mod.main("release-candidate")

    marketplace = tmp_path / ".claude-plugin" / "marketplace.json"
    marketplace.write_text(
        json.dumps(
            {
                "name": "trigger-tree",
                "plugins": [{"name": "trigger-tree", "version": "0.8.0"}],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(SystemExit, match="marketplace plugin version"):
        mod.main("v1.0.0-rc.1")

    (tmp_path / "pkg").mkdir()
    write_release(tmp_path / "pkg")
    monkeypatch.setattr(mod, "ROOT", tmp_path / "pkg")
    (tmp_path / "pkg" / "pyproject.toml").write_text(
        '[project]\nname = "trigger-tree"\nversion = "0.1.0"\n', encoding="utf-8"
    )
    with pytest.raises(SystemExit, match="pyproject packaged version"):
        mod.main("v1.0.0-rc.1")


def test_release_integrity_rejects_inconsistent_codex_metadata(tmp_path, monkeypatch):
    mod = load_release_integrity()
    write_release(tmp_path)
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setattr(mod, "check_docs_currency", lambda _root: None)
    codex = tmp_path / ".codex-plugin" / "plugin.json"
    codex.write_text(json.dumps({"name": "other", "version": "0.9.0"}), encoding="utf-8")
    with pytest.raises(SystemExit, match="names disagree"):
        mod.main("v1.0.0-rc.1")
    codex.write_text(json.dumps({"name": "trigger-tree", "version": "0.9.0"}), encoding="utf-8")
    with pytest.raises(SystemExit, match="Codex plugin version"):
        mod.main("v1.0.0-rc.1")
    codex.write_text(
        json.dumps({"name": "trigger-tree", "version": "1.0.0-rc.1"}), encoding="utf-8"
    )
    (tmp_path / "CHANGELOG.md").write_text(
        "## 0.9.0 — older\n## 1.0.0-rc.1 — buried\n", encoding="utf-8"
    )
    with pytest.raises(SystemExit, match="top CHANGELOG.md release"):
        mod.main("v1.0.0-rc.1")


def test_docs_currency_rejects_induced_command_and_link_drift(tmp_path):
    mod = load_release_integrity()
    (tmp_path / "skills/tt").mkdir(parents=True)
    (tmp_path / "codex-skills/trigger-tree").mkdir(parents=True)
    (tmp_path / "docs").mkdir()
    (tmp_path / "skills/tt/SKILL.md").write_text(
        "---\ndescription: Subcommands /tt status, /tt help.\n---\n"
        '## `$1` = "help" or empty\n| `/tt status` | ok |\n| `/tt help` | ok |\n'
        '## `$1` = "status"\n## `$1` = "help"\n## `$1` = "tips"\n',
        encoding="utf-8",
    )
    (tmp_path / "codex-skills/trigger-tree/SKILL.md").write_text(
        "- Status: run it\n- Tips: run it\n", encoding="utf-8"
    )
    (tmp_path / "index.html").write_text("/tt status", encoding="utf-8")
    (tmp_path / "README.md").write_text("/tt missing\n[broken](docs/gone.md)\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="README.md command drift"):
        mod.check_docs_currency(tmp_path)

    (tmp_path / "README.md").write_text(
        "/tt status — docs\n[broken](docs/gone.md)\n", encoding="utf-8"
    )
    with pytest.raises(SystemExit, match="broken relative link"):
        mod.check_docs_currency(tmp_path)


def test_docs_currency_accepts_real_tree():
    mod = load_release_integrity()
    mod.check_docs_currency(Path(REPO))
