"""Reject release tags that disagree with the plugin's release metadata."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def fail(message: str) -> None:
    raise SystemExit(f"release integrity failed: {message}")


def main(tag: str) -> None:
    if not re.fullmatch(r"v\d+\.\d+\.\d+(?:-rc\.\d+)?", tag):
        fail(f"tag {tag!r} is not vMAJOR.MINOR.PATCH or vMAJOR.MINOR.PATCH-rc.N")

    manifest = json.loads((ROOT / ".claude-plugin/plugin.json").read_text())
    marketplace = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text())
    version = tag.removeprefix("v")

    if manifest["version"] != version:
        fail(f"tag {tag} does not match plugin version {manifest['version']}")
    if marketplace["name"] != manifest["name"]:
        fail("marketplace and plugin names disagree")
    if not any(plugin["name"] == manifest["name"] for plugin in marketplace["plugins"]):
        fail("marketplace does not expose the plugin manifest name")
    entry = next(plugin for plugin in marketplace["plugins"] if plugin["name"] == manifest["name"])
    if entry.get("version") != version:
        fail(f"marketplace plugin version {entry.get('version')} does not match {version}")

    changelog = (ROOT / "CHANGELOG.md").read_text()
    if not re.search(rf"^## (?:\[)?{re.escape(version)}(?:\])?(?:\s|$)", changelog, re.M):
        fail(f"CHANGELOG.md has no {version} release heading")

    print(f"Release metadata consistently describes {tag}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        fail("expected exactly one tag argument")
    main(sys.argv[1])
