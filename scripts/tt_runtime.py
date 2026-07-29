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


def codex_install(script_dir):
    """True when this copy of the plugin lives inside the Codex home.

    The Codex manifest must declare `./skills/` for the portal validator, so a
    marketplace install resolves that to the repository's Claude skill, which
    passes `--client claude`. Where the files physically live is unambiguous
    evidence, so it outranks a flag the wrong skill happened to supply.
    """
    home = os.environ.get("CODEX_HOME") or os.path.join(os.path.expanduser("~"), ".codex")
    try:
        home = os.path.abspath(home)
        return os.path.commonpath([os.path.abspath(script_dir), home]) == home
    except (OSError, ValueError):  # unrelated drives on Windows
        return False


def session_id():
    """Resolve the running client's session id from the process environment.

    Claude Code exports `CLAUDE_CODE_SESSION_ID`. `CLAUDE_SESSION_ID` is only a
    `${...}` template placeholder substituted into hook command strings, so it
    never reaches the environment and reading it alone silently disables every
    check that depends on knowing the live session (issue #21). It stays as a
    fallback because other clients and explicit hook wiring do set it.
    """
    for name in ("CLAUDE_CODE_SESSION_ID", "CLAUDE_SESSION_ID", "TT_SESSION_ID"):
        value = os.environ.get(name)
        if value:
            return value
    return None


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
