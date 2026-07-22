"""Reject release tags that disagree with the plugin's release metadata."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[2]
PUBLIC_OMISSIONS = {"help"}
CLAUDE_SECTION_ONLY = {"tips"}
CODEX_LABELS = {"live dashboard": "watch"}


def fail(message: str) -> None:
    raise SystemExit(f"release integrity failed: {message}")


def tt_commands(text: str) -> set[str]:
    return set(re.findall(r"/tt\s+([a-z]+)", text))


def require_commands(label: str, actual: set[str], expected: set[str]) -> None:
    if actual != expected:
        fail(
            f"{label} command drift: missing {sorted(expected - actual)}, "
            f"extra {sorted(actual - expected)}"
        )


def check_relative_links(root: Path) -> None:
    documents = [root / "README.md", *(root / "docs").glob("*.md")]
    for document in documents:
        text = document.read_text(encoding="utf-8")
        for raw_target in re.findall(r"!?\[[^]]*\]\(([^)]+)\)", text):
            target = raw_target.strip().strip("<>").split("#", 1)[0]
            if not target or re.match(r"^[a-z][a-z0-9+.-]*:", target, re.I):
                continue
            resolved = (document.parent / unquote(target)).resolve()
            if not resolved.exists():
                fail(f"broken relative link in {document.relative_to(root)}: {raw_target}")


def check_docs_currency(root: Path = ROOT) -> None:
    claude = (root / "skills/tt/SKILL.md").read_text(encoding="utf-8")
    frontmatter = claude.split("---", 2)[1]
    help_block = claude.split('## `$1` = "help" or empty', 1)[1].split("\n## ", 1)[0]
    canonical = tt_commands(frontmatter)
    require_commands("Claude help table", tt_commands(help_block), canonical)

    sections = set(re.findall(r'^## `\$1` = "([a-z]+)', claude, re.M))
    require_commands("Claude handler sections", sections - CLAUDE_SECTION_ONLY, canonical)

    public = canonical - PUBLIC_OMISSIONS
    require_commands(
        "README.md", tt_commands((root / "README.md").read_text(encoding="utf-8")), public
    )
    require_commands(
        "index.html", tt_commands((root / "index.html").read_text(encoding="utf-8")), public
    )

    codex = (root / "codex-skills/trigger-tree/SKILL.md").read_text(encoding="utf-8")
    labels = set(re.findall(r"^- ([A-Za-z ]+):", codex, re.M))
    codex_commands = {CODEX_LABELS.get(label.lower(), label.lower()) for label in labels}
    require_commands("Codex workflows", codex_commands, public | CLAUDE_SECTION_ONLY)
    check_relative_links(root)


def main(tag: str) -> None:
    if not re.fullmatch(r"v\d+\.\d+\.\d+(?:-rc\.\d+)?", tag):
        fail(f"tag {tag!r} is not vMAJOR.MINOR.PATCH or vMAJOR.MINOR.PATCH-rc.N")

    manifest = json.loads((ROOT / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))
    codex_manifest = json.loads((ROOT / ".codex-plugin/plugin.json").read_text(encoding="utf-8"))
    marketplace = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text(encoding="utf-8"))
    version = tag.removeprefix("v")

    if manifest["version"] != version:
        fail(f"tag {tag} does not match plugin version {manifest['version']}")
    if codex_manifest["name"] != manifest["name"]:
        fail("Codex and Claude plugin names disagree")
    if codex_manifest["version"] != version:
        fail(f"Codex plugin version {codex_manifest['version']} does not match {version}")
    if marketplace["name"] != manifest["name"]:
        fail("marketplace and plugin names disagree")
    if not any(plugin["name"] == manifest["name"] for plugin in marketplace["plugins"]):
        fail("marketplace does not expose the plugin manifest name")
    entry = next(plugin for plugin in marketplace["plugins"] if plugin["name"] == manifest["name"])
    if entry.get("version") != version:
        fail(f"marketplace plugin version {entry.get('version')} does not match {version}")

    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    packaged = re.search(r'(?m)^version = "([^"]+)"$', pyproject)
    if not packaged or packaged.group(1) != version:
        found = packaged.group(1) if packaged else "missing"
        fail(f"pyproject packaged version {found} does not match {version}")

    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    heading = re.search(r"^## (?:\[)?([^]\s]+)", changelog, re.M)
    if not heading or heading.group(1) != version:
        fail(f"top CHANGELOG.md release is not {version}")

    check_docs_currency(ROOT)

    print(f"Release metadata consistently describes {tag}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        fail("expected exactly one tag argument")
    if sys.argv[1] == "--docs":
        check_docs_currency(ROOT)
        print("User-facing command surfaces and relative links are current")
    else:
        main(sys.argv[1])
