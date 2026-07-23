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


def git_visible_files(root):
    """Every path git considers part of the repository — tracked plus
    untracked-but-not-ignored — or None outside a git repository. The shared
    source of truth for scope and structure inventories (issues #8, #16)."""
    try:
        # Git prints pathnames as UTF-8 bytes on every platform; decoding with the
        # locale (text=True) mangles non-ASCII names on Windows runners.
        result = subprocess.run(
            ["git", "-C", root, "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return {line for line in result.stdout.split("\0") if line}


def _git_markdown(root, limit):
    """Git-visible markdown, so scratch trees never crowd out documentation
    (issue #8). Returns None outside a git repository so the filesystem walk
    stays the fallback."""
    visible = git_visible_files(root)
    if visible is None:
        return None
    names = [
        line
        for line in visible
        if line.lower().endswith((".md", ".markdown"))
        and not any(part in SKIP_DIRS or part.startswith(".venv") for part in line.split("/")[:-1])
    ]
    names.sort()
    return names[:limit], len(names) > limit


def symlinked_surfaces(root, watch_regex, limit=DEFAULT_LIMIT):
    """Directory symlinks whose contents the watch regex would cover.

    Neither git nor the walk follows directory symlinks, so a watched surface
    behind one silently vanishes from every inventory (issue #15). Naming the
    surface keeps the health scope honest without importing bytes from outside
    the repository into a deterministic score.
    """
    pattern = re.compile(watch_regex)
    found = []
    visited = 0
    for current, directories, _files in os.walk(root, followlinks=False):
        keep = []
        for name in directories:
            if name in SKIP_DIRS or name.startswith(".venv"):
                continue
            full = os.path.join(current, name)
            relative = os.path.relpath(full, root).replace(os.sep, "/")
            if os.path.islink(full):
                # Probe: would a markdown child of this directory be watched?
                if pattern.search(relative + "/probe.md"):
                    found.append({"path": relative, "target": os.path.realpath(full)})
                continue
            keep.append(name)
        directories[:] = keep
        visited += 1
        if visited >= limit or len(found) >= 20:
            break
    return sorted(found, key=lambda item: item["path"])


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
