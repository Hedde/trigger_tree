#!/usr/bin/env python3
"""trigger-tree logger — invoked by the plugin hooks. Stdlib only, no jq needed.

Events (first argument):
  session  SessionStart hook
  prompt   UserPromptSubmit hook (respects TT_LOG_PROMPTS: truncate|hash|off)
  read     PostToolUse on Read|Glob|Grep (Read → "read", Glob/Grep → "scan")
  bash     PostToolUse on Bash (rg/grep/find doc targets → "scan";
           cat/head/tail/sed/awk doc files → "read")
  skill    PostToolUse on Skill (logs the skill name)
  note     manual annotation: tt-log.py note "text" (e.g. "sharpened UX router")
  ingest   external adapter entry point: tt-log.py ingest '{"t":"read","path":"docs/x.md"}'
           — lets any tool (a Codex wrapper, a git hook) append telemetry through a
           stable interface. Missing ts/session are stamped; unknown/invalid events
           are dropped silently.

Appends one JSON line per event to $PROJECT/.trigger-tree/history.jsonl and rotates
the file to history-<utc-timestamp>.jsonl when it exceeds TT_ROTATE_BYTES.
Hooks must never disturb the session: every failure exits 0 silently.
"""

import glob
import hashlib
import json
import os
import posixpath
import re
import shlex
import stat
import subprocess
import sys
import tempfile
import time

ROOT = os.environ.get("TT_PROJECT_DIR") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCHEMA_VERSION = 1

DEFAULTS = {
    "TT_WATCH_REGEX": r"^docs/.*\.md$",
    "TT_SCAN_REGEX": r"^docs(/|$)",
    "TT_LOG_PROMPTS": "hash",
    "TT_ROTATE_BYTES": "5242880",
    "TT_EXPERIMENTAL_OUTCOMES": "off",
}


def conf():
    # Layered per key: plugin default first, project override wins where present.
    out = dict(DEFAULTS)
    for path in (
        os.path.join(SCRIPT_DIR, "tt-config.sh"),
        os.path.join(ROOT, ".trigger-tree", "config.sh"),
    ):
        try:
            text = open(path, encoding="utf-8").read()
        except OSError:
            continue
        for key in DEFAULTS:
            m = re.search(key + r"='([^']+)'", text)
            if m:
                out[key] = m.group(1)
    return out


def now_ts():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _session_state_path(hist_dir, session):
    name = hashlib.sha256(str(session).encode("utf-8")).hexdigest()[:32] + ".json"
    return os.path.join(hist_dir, "sessions", name)


def _update_session_state(hist_dir, obj):
    """Keep statusline work bounded and independent from history rotation."""
    if not obj.get("session") or (
        obj.get("t") not in ("session", "read", "scan") and not obj.get("tool_use_id")
    ):
        return
    state_dir = os.path.join(hist_dir, "sessions")
    if os.path.lexists(state_dir):
        mode = os.lstat(state_dir).st_mode
        if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
            return
    else:
        os.makedirs(state_dir, mode=0o700)
    try:
        os.chmod(state_dir, 0o700)
    except OSError:
        pass
    path = _session_state_path(hist_dir, obj["session"])
    seeded_from_history = False
    try:
        state = json.loads(open(path, encoding="utf-8").read())
    except (OSError, ValueError):
        if obj["t"] == "session" and obj.get("source") == "startup":
            # A fresh SessionStart cannot have earlier reads. Create its empty cache
            # now so the first read never scans every archive while holding the lock.
            state = {"files": [], "scans": 0, "last": None, "recent_events": []}
        else:
            # Resume/compaction and pre-cache upgrades may already have history.
            state = _session_state_from_history(hist_dir, obj["session"])
            seeded_from_history = True
    state.setdefault("recent_events", [])
    if obj.get("tool_use_id"):
        state["recent_events"] = (state["recent_events"] + [_event_identity(obj)])[-64:]
    if obj["t"] == "session":
        pass
    elif seeded_from_history:
        # The caller appends before updating the cache, so migration already saw
        # this event in history and must not apply it a second time.
        pass
    elif obj["t"] == "read":
        state["files"] = sorted(set(state.get("files", [])) | {obj["path"]})
        state["last"] = {"t": obj["t"], "path": obj["path"], "ts": obj.get("ts", "")}
    elif obj["t"] == "scan":
        state["scans"] = int(state.get("scans", 0)) + 1
        state["last"] = {"t": obj["t"], "path": obj["path"], "ts": obj.get("ts", "")}
    fd, temporary = tempfile.mkstemp(prefix=".session.", dir=state_dir, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(state, handle, ensure_ascii=False, separators=(",", ":"))
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _session_state_from_history(hist_dir, session):
    files, scans, last = set(), 0, None
    for history in sorted(glob.glob(os.path.join(hist_dir, "history*.jsonl"))):
        try:
            lines = open(history, encoding="utf-8")
        except OSError:
            continue
        with lines:
            for line in lines:
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                if event.get("session") != session or event.get("t") not in ("read", "scan"):
                    continue
                if event["t"] == "read":
                    files.add(event["path"])
                else:
                    scans += 1
                if last is None or event.get("ts", "") >= last.get("ts", ""):
                    last = {"t": event["t"], "path": event["path"], "ts": event.get("ts", "")}
    return {"files": sorted(files), "scans": scans, "last": last, "recent_events": []}


def _event_identity(obj):
    """Return the bounded idempotency identity for one tool-backed event."""
    return [str(obj.get("tool_use_id", "")), str(obj.get("t", "")), str(obj.get("path", ""))]


def _already_recorded(hist_dir, obj):
    """Drop duplicate harness deliveries without scanning telemetry history."""
    if not obj.get("tool_use_id") or not obj.get("session"):
        return False
    path = _session_state_path(hist_dir, obj["session"])
    try:
        mode = os.lstat(path).st_mode
        if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
            return False
        state = json.loads(open(path, encoding="utf-8").read())
    except (OSError, ValueError):
        return False
    return _event_identity(obj) in state.get("recent_events", [])


def append(obj, rotate_bytes):
    obj.setdefault("schema_version", SCHEMA_VERSION)
    hist_dir = os.path.join(ROOT, ".trigger-tree")
    if os.path.lexists(hist_dir):
        mode = os.lstat(hist_dir).st_mode
        if not stat.S_ISDIR(mode) or stat.S_ISLNK(mode):
            return
    else:
        os.makedirs(hist_dir, mode=0o700)
    try:
        os.chmod(hist_dir, 0o700)
    except OSError:
        pass
    lock_path = os.path.join(hist_dir, "write.lock")
    if os.path.lexists(lock_path):
        mode = os.lstat(lock_path).st_mode
        if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
            return
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    lock_fd = os.open(lock_path, flags, 0o600)
    if not stat.S_ISREG(os.fstat(lock_fd).st_mode):
        os.close(lock_fd)
        return
    try:
        if os.name == "nt":  # pragma: no cover - exercised by Windows CI
            import msvcrt

            if os.path.getsize(lock_path) == 0:
                os.write(lock_fd, b"0")
            os.lseek(lock_fd, 0, os.SEEK_SET)
            msvcrt.locking(lock_fd, msvcrt.LK_LOCK, 1)
        else:  # pragma: no cover - POSIX branch, covered on Linux/macOS CI
            import fcntl

            fcntl.flock(lock_fd, fcntl.LOCK_EX)
        _append_locked(obj, rotate_bytes, hist_dir)
    finally:
        if os.name == "nt":  # pragma: no cover - exercised by Windows CI
            import msvcrt

            os.lseek(lock_fd, 0, os.SEEK_SET)
            msvcrt.locking(lock_fd, msvcrt.LK_UNLCK, 1)
        else:  # pragma: no cover - POSIX branch, covered on Linux/macOS CI
            import fcntl

            fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)


def _append_locked(obj, rotate_bytes, hist_dir):
    if _already_recorded(hist_dir, obj):
        return
    hist = os.path.join(hist_dir, "history.jsonl")
    try:
        if os.path.lexists(hist):
            mode = os.lstat(hist).st_mode
            if not stat.S_ISREG(mode) or stat.S_ISLNK(mode):
                return
        if os.path.getsize(hist) > rotate_bytes:
            stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
            archive = os.path.join(hist_dir, f"history-{stamp}.jsonl")
            suffix = 1
            while os.path.exists(archive):
                archive = os.path.join(hist_dir, f"history-{stamp}-{suffix}.jsonl")
                suffix += 1
            os.rename(hist, archive)
            try:
                os.chmod(archive, 0o600)
            except OSError:
                pass
    except OSError:
        pass
    flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT
    flags |= getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(hist, flags, 0o600)
    if not stat.S_ISREG(os.fstat(fd).st_mode):
        os.close(fd)
        return
    try:
        os.chmod(hist, 0o600)
    except OSError:
        pass
    with os.fdopen(fd, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(obj, ensure_ascii=False) + "\n")
    _update_session_state(hist_dir, obj)


def rel_path(target):
    # Normalize to forward slashes so logged paths are identical on all platforms.
    t = target.replace("\\", "/")
    root = ROOT.replace("\\", "/").rstrip("/") + "/"
    return t[len(root) :] if t.startswith(root) else t


def shell_segments(command):
    """Tokenize a shell command without executing it, split at control operators."""
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars="|;&")
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:
        return []
    segments, current = [], []
    for token in tokens:
        if token and all(ch in "|;&" for ch in token):
            if current:
                segments.append(current)
                current = []
        else:
            current.append(token)
    if current:
        segments.append(current)
    return segments


def bash_scan_paths(command, scan_regex):
    """Return doc targets of explicit rg/grep/find commands, never their contents.

    Only existing path arguments are considered. This deliberately avoids guessing
    that arbitrary Bash commands or search patterns are documentation lookups.
    Multiple file arguments collapse to their common directory so one shell search
    produces one scan event rather than inflating the hunting count.
    """
    found = []
    for segment in shell_segments(command):
        tool_i = None
        for i, token in enumerate(segment):
            if os.path.basename(token).lower() in ("rg", "grep", "find"):
                tool_i = i
                break
        if tool_i is None:
            continue
        targets = []
        for token in segment[tool_i + 1 :]:
            candidate = token if os.path.isabs(token) else os.path.join(ROOT, token)
            if os.path.exists(candidate):
                rel = rel_path(os.path.abspath(candidate)).rstrip("/") or "."
                if re.search(scan_regex, rel):
                    targets.append(rel if os.path.isdir(candidate) else posixpath.dirname(rel))
        targets = [target for target in targets if target]
        if targets:
            common = posixpath.commonpath(targets)
            if common not in found and re.search(scan_regex, common):
                found.append(common)
    return found


def bash_read_paths(command, watch_regex):
    """Return existing watched files explicitly consumed by shell reader commands."""
    found = []
    readers = ("cat", "head", "tail", "sed", "awk", "get-content", "gc", "type")
    for segment in shell_segments(command):
        tool_i = None
        for i, token in enumerate(segment):
            if os.path.basename(token).lower() in readers:
                tool_i = i
                break
        if tool_i is None:
            continue
        tool = os.path.basename(segment[tool_i]).lower()
        for rel in reader_arg_paths(tool, segment[tool_i + 1 :], watch_regex):
            if rel not in found:
                found.append(rel)
    return found


def reader_arg_paths(tool, arguments, watch_regex, base_dir=None):
    """Filter expanded reader argv down to existing watched file paths."""
    if tool == "sed" and any(
        token == "--in-place" or token.startswith("--in-place=") or re.match(r"^-i", token)
        for token in arguments
    ):
        return []
    base_dir = ROOT if base_dir is None else base_dir
    found = []
    for token in arguments:
        candidate = token if os.path.isabs(token) else os.path.join(base_dir, token)
        if not os.path.isfile(candidate):
            continue
        rel = rel_path(os.path.abspath(candidate))
        if re.search(watch_regex, rel) and rel not in found:
            found.append(rel)
    return found


def watch_suffix_hint(pattern):
    """Return one safe extension hint only when every regex branch shares it."""
    suffixes = {f".{value}" for value in re.findall(r"\\\.([A-Za-z0-9]+)\$", pattern)}
    return suffixes.pop() if len(suffixes) == 1 else ""


def configure_shell_capture(session, watch_regex):
    """Persist runtime reader wrappers into Claude Code's Bash preamble."""
    env_file = os.environ.get("CLAUDE_ENV_FILE")
    shell_capture = os.path.join(SCRIPT_DIR, "tt-shell-capture.sh")
    if not env_file or not os.path.isfile(shell_capture):
        return
    values = {
        "TT_SHELL_LOGGER": os.path.join(SCRIPT_DIR, "tt-log.py"),
        "TT_SHELL_SESSION": session,
        "TT_SHELL_WATCH_SUFFIX": watch_suffix_hint(watch_regex),
    }
    try:
        with open(env_file, "a", encoding="utf-8") as fh:
            fh.write("\n# trigger-tree runtime Bash read capture\n")
            for key, value in values.items():
                fh.write(f"export {key}={shlex.quote(value)}\n")
            fh.write(f". {shlex.quote(shell_capture)}\n")
    except OSError:
        pass


def git_head():
    try:
        return (
            subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=2,
                check=True,
            ).stdout.strip()
            or None
        )
    except (OSError, subprocess.SubprocessError):
        return None


def looks_like_test_command(command):
    for segment in shell_segments(command):
        words = [os.path.basename(word).lower() for word in segment]
        if words[0] in ("pytest", "py.test") or words[:2] in (["cargo", "test"], ["go", "test"]):
            return True
        if (
            len(words) >= 2
            and words[0] in ("npm", "pnpm", "yarn", "bun")
            and words[1]
            in (
                "test",
                "run",
            )
        ):
            return True
        if words[:2] in (["mix", "test"], ["swift", "test"], ["dotnet", "test"]):
            return True
    return False


def session_signals(session):
    baseline = test_status = None
    paths = sorted(glob.glob(os.path.join(ROOT, ".trigger-tree", "history*.jsonl")))
    for path in paths:
        try:
            lines = open(path, encoding="utf-8", errors="replace")
        except OSError:
            continue
        with lines:
            for line in lines:
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(event, dict) or event.get("session") != session:
                    continue
                if event.get("t") == "session" and event.get("git_head") and baseline is None:
                    baseline = event["git_head"]
                elif event.get("t") == "test":
                    test_status = event.get("status")
    return baseline, test_status


def main():
    event = sys.argv[1] if len(sys.argv) > 1 else ""
    cfg = conf()
    rotate = int(cfg["TT_ROTATE_BYTES"])
    ts = now_ts()

    if event == "ingest":
        try:
            obj = json.loads(sys.argv[2])
        except (IndexError, json.JSONDecodeError):
            return
        if obj.get("t") not in (
            "read",
            "scan",
            "skill",
            "note",
            "prompt",
            "session",
            "test",
            "outcome",
        ):
            return
        if obj["t"] in ("read", "scan"):
            if not obj.get("path"):
                return
            obj["path"] = rel_path(str(obj["path"]))
        obj.setdefault("ts", ts)
        obj.setdefault("session", os.environ.get("CLAUDE_SESSION_ID", "external"))
        obj.setdefault("agent", "external")
        append(obj, rotate)
        return

    if event == "shell-read":
        tool = os.path.basename(sys.argv[2]).lower() if len(sys.argv) > 2 else ""
        if tool not in ("cat", "head", "tail", "sed", "awk", "get-content", "gc", "type"):
            return
        session = os.environ.get("TT_SHELL_SESSION") or os.environ.get("CLAUDE_SESSION_ID", "?")
        for path in reader_arg_paths(tool, sys.argv[3:], cfg["TT_WATCH_REGEX"], os.getcwd()):
            append(
                {
                    "t": "read",
                    "ts": ts,
                    "session": session,
                    "tool": "Bash",
                    "path": path,
                    "agent": "runtime",
                    "capture": "expanded-argv",
                },
                rotate,
            )
        return

    if event == "note":
        text = " ".join(sys.argv[2:]).strip()[:300]
        if text:
            session = os.environ.get("CLAUDE_SESSION_ID", "?")
            append({"t": "note", "ts": ts, "session": session, "text": text}, rotate)
        return

    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        data = {}
    session = data.get("session_id", "?")
    agent = data.get("agent_type", "main")
    agent_id = data.get("agent_id")

    def hook_identity(entry):
        if data.get("tool_use_id"):
            entry["tool_use_id"] = data["tool_use_id"]
        if agent_id:
            entry["agent_id"] = agent_id
        return entry

    if event == "session":
        configure_shell_capture(session, cfg["TT_WATCH_REGEX"])
        append(
            {
                "t": "session",
                "ts": ts,
                "session": session,
                "source": data.get("source", "unknown"),
                "git_head": git_head(),
            },
            rotate,
        )

    elif event == "prompt":
        entry = {"t": "prompt", "ts": ts, "session": session}
        mode = cfg["TT_LOG_PROMPTS"]
        prompt = (data.get("prompt") or "").replace("\n", " ")
        if mode == "truncate":
            entry["prompt"] = prompt[:200]
        elif mode == "hash":
            entry["prompt_hash"] = hashlib.sha1(prompt.encode()).hexdigest()[:10]
        # mode "off": marker only — fingerprints still work, no prompt text stored
        append(entry, rotate)

    elif event == "read":
        tool = data.get("tool_name", "?")
        tool_input = data.get("tool_input") or {}
        if tool == "Read":
            target, typ, regex = tool_input.get("file_path"), "read", cfg["TT_WATCH_REGEX"]
        else:
            target, typ, regex = tool_input.get("path"), "scan", cfg["TT_SCAN_REGEX"]
        if not target:
            return
        rel = rel_path(target)
        if not re.search(regex, rel):
            return
        append(
            hook_identity(
                {"t": typ, "ts": ts, "session": session, "tool": tool, "path": rel, "agent": agent}
            ),
            rotate,
        )

    elif event == "bash":
        command = (data.get("tool_input") or {}).get("command", "")
        if looks_like_test_command(command):
            append({"t": "test", "ts": ts, "session": session, "status": "pass"}, rotate)
        if os.environ.get("TT_RUNTIME_BASH_READS") != "1":
            for path in bash_read_paths(command, cfg["TT_WATCH_REGEX"]):
                append(
                    hook_identity(
                        {
                            "t": "read",
                            "ts": ts,
                            "session": session,
                            "tool": "Bash",
                            "path": path,
                            "agent": agent,
                        }
                    ),
                    rotate,
                )
        for path in bash_scan_paths(command, cfg["TT_SCAN_REGEX"]):
            append(
                hook_identity(
                    {
                        "t": "scan",
                        "ts": ts,
                        "session": session,
                        "tool": "Bash",
                        "path": path,
                        "agent": agent,
                    }
                ),
                rotate,
            )

    elif event == "bash-failure":
        command = (data.get("tool_input") or {}).get("command", "")
        if looks_like_test_command(command):
            append({"t": "test", "ts": ts, "session": session, "status": "fail"}, rotate)

    elif event == "outcome":
        baseline, test_status = session_signals(session)
        current = git_head()
        append(
            {
                "t": "outcome",
                "ts": ts,
                "session": session,
                "git_commit_landed": bool(baseline and current and baseline != current),
                "test_status": test_status or "unknown",
                "source": data.get("reason", "unknown"),
            },
            rotate,
        )

    elif event == "skill":
        name = (data.get("tool_input") or {}).get("skill", "")
        if name:
            append(
                hook_identity(
                    {"t": "skill", "ts": ts, "session": session, "skill": name, "agent": agent}
                ),
                rotate,
            )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass  # a logging failure must never break the session
    sys.exit(0)
