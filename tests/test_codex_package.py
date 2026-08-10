import importlib.util
import json
import re
import stat
from pathlib import Path
from zipfile import ZipFile

from conftest import REPO

ROOT = Path(REPO)


def load_codex_builder():
    path = ROOT / ".github" / "scripts" / "build_codex_zip.py"
    spec = importlib.util.spec_from_file_location("build_codex_zip_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_codex_manifest_is_complete_and_references_real_components():
    manifest = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    claude = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert manifest["name"] == claude["name"] == "trigger-tree"
    assert manifest["version"] == claude["version"]
    assert manifest["skills"] == "./skills/"
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


def test_codex_marketplace_installs_the_checkout_itself():
    market = json.loads(
        (ROOT / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8")
    )
    assert market["name"] == "trigger-tree"
    assert market["interface"]["displayName"] == "trigger-tree"
    assert len(market["plugins"]) == 1
    entry = market["plugins"][0]
    assert entry["name"] == "trigger-tree"
    # Relatief, zodat een op een tag gepinde marketplace-checkout zijn eigen
    # bytes installeert — een hardcoded url+ref volgde altijd main (issue #6).
    # Objectvorm i.p.v. kale string: de HOL Guard scanner eist source.path.
    assert entry["source"] == {"source": "local", "path": "./"}
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
        "tt-instructions.py",
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


def test_codex_upload_archive_is_complete_and_reproducible(tmp_path):
    builder = load_codex_builder()
    first = builder.build(tmp_path / "first.zip")
    second = builder.build(tmp_path / "second.zip")
    assert first.read_bytes() == second.read_bytes()

    with ZipFile(first) as archive:
        entries = archive.infolist()
        assert [entry.filename for entry in entries] == sorted(
            [entry.filename for entry in entries]
        )
        assert len(entries) == len({entry.filename for entry in entries})
        assert all(entry.date_time == builder.TIMESTAMP for entry in entries)
        names = {entry.filename for entry in entries}
        assert "scripts/tt-instructions.py" in names
        assert "scripts/tt_adherence.py" in names
        assert "scripts/tt_runtime.py" in names
        assert "scripts/tt_scope.py" in names
        assert "skills/trigger-tree/SKILL.md" in names
        assert "codex-skills/trigger-tree/SKILL.md" not in names
        packaged_manifest = json.loads(archive.read(".codex-plugin/plugin.json").decode("utf-8"))
        skills_root = packaged_manifest["skills"].removeprefix("./").rstrip("/")
        assert skills_root == "skills"
        assert any(
            name.startswith(f"{skills_root}/") and name.endswith("/SKILL.md") for name in names
        )
        assert names == set(builder.FILES.values()) | {
            f"{parent.as_posix()}/"
            for destination in builder.FILES.values()
            for parent in Path(destination).parents
            if str(parent) != "."
        }
        by_name = {entry.filename: entry for entry in entries}
        assert stat.S_IMODE(by_name["scripts/tt-log.py"].external_attr >> 16) == 0o755
        assert stat.S_IMODE(by_name["scripts/tt_adherence.py"].external_attr >> 16) == 0o644
