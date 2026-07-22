"""Bounded, local audit of Markdown files covered by trigger-tree's watch regex."""

import os
import re

DEFAULT_LIMIT = 5000
SKIP_DIRS = {
    ".git",
    ".agents",
    ".codex",
    ".pytest_cache",
    ".trigger-tree",
    "node_modules",
    "vendor",
    "vendors",
    "dist",
    "build",
    "__pycache__",
    "tests",
    "worktrees",
}


def scan_markdown(root, watch_regex, limit=DEFAULT_LIMIT):
    """Return visited/Markdown/watched counts without following links or walking forever."""
    pattern = re.compile(watch_regex)
    visited = markdown = watched = 0
    paths = []
    capped = False
    for current, directories, files in os.walk(root, followlinks=False):
        directories[:] = [
            name for name in directories if name not in SKIP_DIRS and not name.startswith(".venv")
        ]
        for name in files:
            if visited >= limit:
                capped = True
                return {
                    "visited": visited,
                    "markdown": markdown,
                    "watched": watched,
                    "paths": paths,
                    "capped": capped,
                }
            visited += 1
            if not name.lower().endswith((".md", ".markdown")):
                continue
            markdown += 1
            relative = os.path.relpath(os.path.join(current, name), root).replace(os.sep, "/")
            paths.append(relative)
            watched += bool(pattern.search(relative))
    return {
        "visited": visited,
        "markdown": markdown,
        "watched": watched,
        "paths": paths,
        "capped": capped,
    }


def suggested_regex(paths):
    """Describe only observed Markdown locations, without inventing repository intent."""
    roots = sorted({path.split("/", 1)[0] for path in paths if "/" in path})
    files = sorted(path for path in paths if "/" not in path)
    parts = []
    if roots:
        parts.append(
            r"^(?:" + "|".join(re.escape(name) for name in roots) + r")/.*\.(?:md|markdown)$"
        )
    if files:
        parts.append(r"^(?:" + "|".join(re.escape(name) for name in files) + r")$")
    return "|".join(parts)


def is_poor_coverage(result):
    total = result["markdown"]
    return total > 0 and (result["watched"] == 0 or result["watched"] / total < 0.25)
