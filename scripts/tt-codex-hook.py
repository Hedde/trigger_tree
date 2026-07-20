#!/usr/bin/env python3
"""Translate Codex lifecycle hooks to trigger-tree's stable logger contract."""

import io
import json
import os
import runpy
import subprocess
import sys


def read_payload(stream):
    try:
        value = json.load(stream)
    except (json.JSONDecodeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def normalize_tool(payload):
    tool = payload.get("tool_name", "")
    tool_input = payload.get("tool_input")
    tool_input = dict(tool_input) if isinstance(tool_input, dict) else {}

    if tool == "Bash":
        tool_input["command"] = tool_input.get("command") or tool_input.get("cmd", "")
        route = "bash"
    elif tool in ("Read", "Glob", "Grep"):
        route = "read"
    elif tool.startswith("mcp__"):
        target = next(
            (
                tool_input.get(key)
                for key in ("file_path", "path", "filename", "uri")
                if tool_input.get(key)
            ),
            None,
        )
        if not target or str(target).startswith(("http://", "https://")):
            return None, payload
        is_search = any(word in tool.lower() for word in ("search", "grep", "find"))
        tool_input = {"path" if is_search else "file_path": target}
        tool = "Grep" if is_search else "Read"
        route = "read"
    else:
        return None, payload

    normalized = dict(payload)
    normalized["tool_name"] = tool
    normalized["tool_input"] = tool_input
    return route, normalized


def translate(payload):
    event = payload.get("hook_event_name", "")
    if event == "SessionStart":
        normalized = dict(payload)
        normalized["source"] = payload.get("source", "codex")
        return "session", normalized
    if event == "UserPromptSubmit":
        return "prompt", payload
    if event == "PostToolUse":
        return normalize_tool(payload)
    if event == "Stop":
        normalized = dict(payload)
        normalized["reason"] = payload.get("reason", "codex-stop")
        return "outcome", normalized
    return None, payload


def project_root(cwd):
    """Use the repository root so starting Codex in a subdirectory keeps one dataset."""
    try:
        return (
            subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                cwd=cwd or os.getcwd(),
                capture_output=True,
                text=True,
                timeout=2,
                check=True,
            ).stdout.strip()
            or cwd
            or os.getcwd()
        )
    except (OSError, subprocess.SubprocessError):
        return cwd or os.getcwd()


def main():
    payload = read_payload(sys.stdin)
    route, normalized = translate(payload)
    if not route:
        return

    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tt-log.py")
    old_argv, old_stdin = sys.argv, sys.stdin
    old_root = os.environ.get("TT_PROJECT_DIR")
    try:
        os.environ["TT_PROJECT_DIR"] = project_root(normalized.get("cwd"))
        sys.argv = [script, route]
        sys.stdin = io.StringIO(json.dumps(normalized))
        runpy.run_path(script, run_name="__main__")
    except SystemExit:
        pass
    finally:
        sys.argv, sys.stdin = old_argv, old_stdin
        if old_root is None:
            os.environ.pop("TT_PROJECT_DIR", None)
        else:
            os.environ["TT_PROJECT_DIR"] = old_root


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
