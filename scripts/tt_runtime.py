"""Shared runtime path resolution for trigger-tree hook entry points."""

import os
import subprocess


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
