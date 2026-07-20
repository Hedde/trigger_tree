import json
from pathlib import Path

from conftest import REPO

ROOT = Path(REPO)


def test_codex_manifest_is_complete_and_references_real_components():
    manifest = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text())
    claude = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
    assert manifest["name"] == claude["name"] == "trigger-tree"
    assert manifest["version"] == claude["version"]
    assert manifest["skills"] == "./skills/"
    assert "hooks" not in manifest  # Codex discovers hooks/hooks.json by convention.
    assert (ROOT / "skills" / "trigger-tree" / "SKILL.md").is_file()
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
    market = json.loads((ROOT / ".agents" / "plugins" / "marketplace.json").read_text())
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
    text = (ROOT / "skills" / "trigger-tree" / "SKILL.md").read_text()
    assert text.startswith("---\nname: trigger-tree\n")
    assert "description:" in text.split("---", 2)[1]
    assert "[TODO:" not in text
    assert "official Codex lifecycle hooks" in text
