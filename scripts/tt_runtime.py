"""Shared runtime path resolution for trigger-tree hook entry points."""

import os
import subprocess


def user_config_path():
    """User-wide overrides (issue #13): between the bundled defaults and the
    project file, so one person can set a privacy default for every repository
    before any project has run setup. TT_USER_CONFIG points elsewhere if set."""
    explicit = os.environ.get("TT_USER_CONFIG")
    if explicit:
        return explicit
    return os.path.join(os.path.expanduser("~"), ".trigger-tree", "config.sh")


def project_root(cwd=None):
    """Resolve one dataset root: explicit override, git root, Claude root, then cwd."""
    explicit = os.environ.get("TT_PROJECT_DIR")
    if explicit:
        return explicit
    claude_root = os.environ.get("CLAUDE_PROJECT_DIR")
    working = cwd or claude_root or os.getcwd()
    try:
        root = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=working,
            capture_output=True,
            text=True,
            timeout=2,
            check=True,
        ).stdout.strip()
        if root:
            return root
    except (OSError, subprocess.SubprocessError):
        pass
    return claude_root or cwd or os.getcwd()
