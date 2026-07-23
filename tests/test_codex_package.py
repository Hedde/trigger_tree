import json
import re
from pathlib import Path

from conftest import REPO

ROOT = Path(REPO)


def test_codex_manifest_is_complete_and_references_real_components():
    manifest = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    claude = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert manifest["name"] == claude["name"] == "trigger-tree"
    assert manifest["version"] == claude["version"]
    assert manifest["skills"] == "./codex-skills/"
    assert "hooks" not in manifest  # Codex discovers hooks/hooks.json by convention.
    assert (ROOT / "codex-skills" / "trigger-tree" / "SKILL.md").is_file()
    assert (ROOT / "skills" / "tt" / "SKILL.md").is_file()
    assert not (ROOT / "skills" / "trigger-tree").exists()
    assert not (ROOT / "SKILL.md").exists()
    assert (ROOT / "hooks" / "hooks.json").is_file()

    interface = manifest["interface"]
    assert interface["displayName"] == "trigger-tree"
    assert interface["websiteURL"].startswith("https://")
    assert interface["privacyPolicyURL"].startswith("https://")
    assert 1 <= len(interface["defaultPrompt"]) <= 3
    assert all(len(prompt) <= 128 for prompt in interface["defaultPrompt"])
    for field in ("composerIcon", "logo"):
        assert (ROOT / interface[field].removeprefix("./")).is_file()


def test_codex_marketplace_installs_repository_root_from_git():
    market = json.loads(
        (ROOT / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8")
    )
    assert market["name"] == "trigger-tree"
    assert market["interface"]["displayName"] == "trigger-tree"
    assert len(market["plugins"]) == 1
    entry = market["plugins"][0]
    assert entry["name"] == "trigger-tree"
    assert entry["source"] == {
        "source": "url",
        "url": "https://github.com/Hedde/trigger_tree.git",
        "ref": "main",
    }
    assert entry["policy"] == {
        "installation": "AVAILABLE",
        "authentication": "ON_INSTALL",
    }
    assert entry["category"] == "Developer Tools"


def test_codex_skill_has_valid_frontmatter_and_no_placeholders():
    text = (ROOT / "codex-skills" / "trigger-tree" / "SKILL.md").read_text(encoding="utf-8")
    assert text.startswith("---\nname: trigger-tree\n")
    assert "description:" in text.split("---", 2)[1]
    assert "[TODO:" not in text
    assert "official Codex lifecycle hooks" in text
    assert 'TT_PROJECT_DIR="$PWD" TT_CLIENT=codex "$PLUGIN/scripts/tt-open.sh"' in text
    assert text.count('TT_PROJECT_DIR="$PWD"') >= 10
    assert "never `cd` into" in text


def test_claude_command_contract_uses_plugin_root_and_only_real_scripts():
    text = (ROOT / "skills" / "tt" / "SKILL.md").read_text(encoding="utf-8")
    assert "CLAUDE_SKILL_DIR" not in text
    assert "disable-model-invocation: true" in text.split("---", 2)[1]
    references = re.findall(r"\$\{CLAUDE_PLUGIN_ROOT\}/scripts/([\w.-]+)", text)
    assert set(references) == {
        "tt-doctor.py",
        "tt-gate.py",
        "tt-log.py",
        "tt-open.sh",
        "tt-report.py",
        "tt-setup.py",
        "tt-stats.py",
        "tt-suggestions.py",
        "tt-tips.py",
        "tt-uninstall.py",
    }
    assert all((ROOT / "scripts" / name).is_file() for name in references)
    assert 'TT_CLIENT=claude "${CLAUDE_PLUGIN_ROOT}/scripts/tt-open.sh"' in text
    assert "zero to three, never a quota" in text
    assert "silently verify against the repository" in text
    assert "not proof of failed routing" in text
