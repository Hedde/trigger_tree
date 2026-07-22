"""Print the GitHub Release body for one tag from the changelog. Idempotent input."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

FOOTER = """
---

**Install (Claude Code)**

```
/plugin marketplace add Hedde/trigger_tree
/plugin install trigger-tree@trigger-tree
```

**Install (Codex)**

```
codex plugin marketplace add Hedde/trigger_tree
codex plugin install trigger-tree
```

[Website](https://hedde.github.io/trigger_tree/) · [Documentation](https://github.com/Hedde/trigger_tree/tree/main/docs) · [Changelog](https://github.com/Hedde/trigger_tree/blob/main/CHANGELOG.md) · [Privacy](https://github.com/Hedde/trigger_tree/blob/main/PRIVACY.md)
"""


def changelog_section(text: str, version: str) -> str:
    """Return the changelog body for exactly this version, without its heading."""
    pattern = rf"(?ms)^## {re.escape(version)} — [0-9-]+\n(.*?)(?=^## |\Z)"
    match = re.search(pattern, text)
    if not match:
        raise SystemExit(f"CHANGELOG.md has no section for version {version}")
    body = match.group(1).strip()
    if not body:
        raise SystemExit(f"CHANGELOG.md section for {version} is empty")
    return body


def release_body(tag: str, changelog_text: str) -> str:
    version = tag.removeprefix("v")
    return changelog_section(changelog_text, version) + "\n" + FOOTER


def main(tag: str) -> None:
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    sys.stdout.write(release_body(tag, changelog))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: release_notes.py <tag>")
    main(sys.argv[1])
