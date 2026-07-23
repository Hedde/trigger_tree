"""Bounded, local audit of Markdown files covered by trigger-tree's watch regex."""

import os
import re
import subprocess
from fnmatch import fnmatch

DEFAULT_LIMIT = 5000
# .agents and .codex are deliberately NOT skipped: they are valid Codex
# documentation locations a watch regex may target (issue #8).
SKIP_DIRS = {
    ".git",
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


def parse_ignore(value):
    """Split a comma-separated glob list; empty entries drop out."""
    return tuple(glob.strip() for glob in (value or "").split(",") if glob.strip())


def is_ignored(path, ignore_globs):
    return any(fnmatch(path, glob) for glob in ignore_globs)


def _git_markdown(root, limit):
    """Tracked plus untracked-but-not-ignored markdown, straight from git.

    Git's view respects the repository's own .gitignore, so scratch trees never
    crowd out documentation (issue #8). Returns None outside a git repository so
    the filesystem walk stays the fallback.
    """
    try:
        result = subprocess.run(
            ["git", "-C", root, "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    names = [
        line
        for line in result.stdout.split("\0")
        if line.lower().endswith((".md", ".markdown"))
        and not any(part in SKIP_DIRS or part.startswith(".venv") for part in line.split("/")[:-1])
    ]
    names.sort()
    return names[:limit], len(names) > limit


def scan_markdown(root, watch_regex, limit=DEFAULT_LIMIT, ignore_globs=()):
    """Return visited/Markdown/watched counts without following links or walking forever.

    Paths matching an ignore glob are acknowledged as intentionally unwatched and
    leave both the path list and the markdown denominator — unless the watch regex
    matches them, because a watched doc can never be ignored away.
    """
    pattern = re.compile(watch_regex)
    visited = markdown = watched = 0
    paths = []
    capped = False
    candidates = _git_markdown(root, limit)
    if candidates is not None:
        files, capped = candidates
        for relative in files:
            visited += 1
            is_watched = bool(pattern.search(relative))
            if not is_watched and is_ignored(relative, ignore_globs):
                continue
            markdown += 1
            paths.append(relative)
            watched += is_watched
        return {
            "visited": visited,
            "markdown": markdown,
            "watched": watched,
            "paths": paths,
            "capped": capped,
        }
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
            relative = os.path.relpath(os.path.join(current, name), root).replace(os.sep, "/")
            is_watched = bool(pattern.search(relative))
            if not is_watched and is_ignored(relative, ignore_globs):
                continue
            markdown += 1
            paths.append(relative)
            watched += is_watched
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
