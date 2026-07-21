import io
import json
import os
import shlex
import shutil
import stat
import subprocess
import sys

import pytest
from conftest import load_script


def run_main(mod, monkeypatch, argv, stdin_text="{}"):
    monkeypatch.setattr(sys, "argv", ["tt-log.py"] + argv)
    monkeypatch.setattr(sys, "stdin", io.StringIO(stdin_text))
    mod.main()


def read_history(project):
    path = os.path.join(project, ".trigger-tree", "history.jsonl")
    return (
        [json.loads(line) for line in open(path, encoding="utf-8")] if os.path.isfile(path) else []
    )


def test_rel_path(tmp_path):
    mod = load_script("tt-log.py", tmp_path)
    assert mod.rel_path(str(tmp_path / "docs" / "a.md")) == "docs/a.md"
    assert mod.rel_path("/elsewhere/x.md") == "/elsewhere/x.md"


@pytest.mark.skipif(os.name == "nt", reason="Windows does not implement POSIX permission bits")
def test_history_is_private(tmp_path, monkeypatch):
    mod = load_script("tt-log.py", tmp_path)
    run_main(mod, monkeypatch, ["prompt"], '{"session_id":"S","prompt":"hello"}')
    telemetry = tmp_path / ".trigger-tree"
    history = telemetry / "history.jsonl"
    assert stat.S_IMODE(telemetry.stat().st_mode) == 0o700
    assert stat.S_IMODE(history.stat().st_mode) == 0o600


def test_logger_maintains_bounded_statusline_summary_across_rotation(tmp_path):
    mod = load_script("tt-log.py", tmp_path)
    first = {"t": "read", "session": "S", "path": "docs/a.md", "ts": mod.now_ts()}
    second = {"t": "scan", "session": "S", "path": "docs", "ts": mod.now_ts()}
    mod.append(first, 1)
    mod.append(second, 1)
    state_path = mod._session_state_path(str(tmp_path / ".trigger-tree"), "S")
    state = json.loads(open(state_path, encoding="utf-8").read())
    assert state["files"] == ["docs/a.md"]
    assert state["scans"] == 1
    assert state["last"]["path"] == "docs"
    assert list((tmp_path / ".trigger-tree").glob("history-*.jsonl"))


def test_session_summary_migrates_existing_rotated_history_without_reset(tmp_path):
    telemetry = tmp_path / ".trigger-tree"
    telemetry.mkdir()
    old = telemetry / "history-old.jsonl"
    old.write_text(
        "not json\n"
        + json.dumps(
            {"t": "read", "session": "S", "path": "docs/old.md", "ts": "2026-01-01T00:00:00Z"}
        )
        + "\n"
        + json.dumps({"t": "scan", "session": "S", "path": "docs", "ts": "2026-01-02T00:00:00Z"})
        + "\n"
    )
    mod = load_script("tt-log.py", tmp_path)
    event = {"t": "read", "session": "S", "path": "docs/new.md", "ts": "2026-01-03T00:00:00Z"}
    mod.append(event, 1000)
    state = json.loads(open(mod._session_state_path(str(telemetry), "S"), encoding="utf-8").read())
    assert state == {
        "files": ["docs/new.md", "docs/old.md"],
        "scans": 1,
        "last": {"t": "read", "path": "docs/new.md", "ts": "2026-01-03T00:00:00Z"},
    }


def test_session_summary_skips_history_that_disappears(tmp_path, monkeypatch):
    mod = load_script("tt-log.py", tmp_path)
    missing = str(tmp_path / "history-gone.jsonl")
    monkeypatch.setattr(mod.glob, "glob", lambda _pattern: [missing])
    assert mod._session_state_from_history(str(tmp_path), "S") == {
        "files": [],
        "scans": 0,
        "last": None,
    }


def test_session_summary_atomic_cleanup_and_nonregular_history_fd(tmp_path, monkeypatch):
    mod = load_script("tt-log.py", tmp_path)
    telemetry = tmp_path / ".trigger-tree"
    telemetry.mkdir()
    event = {"t": "read", "session": "S", "path": "docs/a.md", "ts": mod.now_ts()}
    real_replace = mod.os.replace
    monkeypatch.setattr(mod.os, "replace", lambda *_args: (_ for _ in ()).throw(OSError("full")))
    with pytest.raises(OSError):
        mod._update_session_state(str(telemetry), event)
    assert not list((telemetry / "sessions").glob(".session.*"))
    monkeypatch.setattr(mod.os, "replace", real_replace)

    real_open = mod.os.open
    calls = 0
    read_fd, write_fd = os.pipe()
    os.close(read_fd)

    def history_is_pipe(path, flags, mode=0o777):
        nonlocal calls
        calls += 1
        return write_fd if calls == 2 else real_open(path, flags, mode)

    monkeypatch.setattr(mod.os, "open", history_is_pipe)
    mod.append(event, 1000)


@pytest.mark.skipif(os.name == "nt", reason="symlink creation needs elevated rights on Windows")
def test_history_symlink_is_never_followed(tmp_path, monkeypatch):
    telemetry = tmp_path / ".trigger-tree"
    telemetry.mkdir()
    victim = tmp_path / "victim"
    victim.write_text("untouched\n")
    (telemetry / "history.jsonl").symlink_to(victim)
    mod = load_script("tt-log.py", tmp_path)
    run_main(mod, monkeypatch, ["prompt"], '{"session_id":"S","prompt":"secret"}')
    assert victim.read_text() == "untouched\n"


def test_secure_append_rejects_non_directory_and_non_regular_fd(tmp_path, monkeypatch):
    mod = load_script("tt-log.py", tmp_path)
    (tmp_path / ".trigger-tree").write_text("not a directory")
    mod.append({"t": "prompt"}, 100)

    (tmp_path / ".trigger-tree").unlink()
    (tmp_path / ".trigger-tree").mkdir()
    read_fd, write_fd = os.pipe()
    os.close(read_fd)
    monkeypatch.setattr(mod.os, "open", lambda *_args, **_kwargs: write_fd)
    mod.append({"t": "prompt"}, 100)


def test_secure_append_rejects_nonregular_history_path_portably(tmp_path):
    telemetry = tmp_path / ".trigger-tree"
    telemetry.mkdir()
    (telemetry / "history.jsonl").mkdir()
    mod = load_script("tt-log.py", tmp_path)
    mod.append({"t": "prompt"}, 100)
    assert (telemetry / "history.jsonl").is_dir()


def test_secure_append_permission_hardening_is_best_effort(tmp_path, monkeypatch):
    mod = load_script("tt-log.py", tmp_path)
    real_chmod = mod.os.chmod

    def selective_chmod(path, mode):
        if str(path).endswith(".trigger-tree") or str(path).endswith("history.jsonl"):
            raise OSError("unsupported")
        return real_chmod(path, mode)

    monkeypatch.setattr(mod.os, "chmod", selective_chmod)
    mod.append({"t": "prompt"}, 100)
    assert (tmp_path / ".trigger-tree" / "history.jsonl").is_file()


def test_rotated_archive_permission_hardening_is_best_effort(tmp_path, monkeypatch):
    telemetry = tmp_path / ".trigger-tree"
    telemetry.mkdir()
    (telemetry / "history.jsonl").write_text("old data")
    mod = load_script("tt-log.py", tmp_path)
    real_chmod = mod.os.chmod

    def archive_chmod(path, mode):
        if "history-" in str(path):
            raise OSError("unsupported")
        return real_chmod(path, mode)

    monkeypatch.setattr(mod.os, "chmod", archive_chmod)
    mod.append({"t": "prompt"}, 1)
    assert list(telemetry.glob("history-*.jsonl"))


@pytest.mark.skipif(os.name == "nt", reason="chmod 0 does not block reads on Windows")
def test_conf_unreadable_falls_back_to_defaults(tmp_path):
    cfg = tmp_path / ".trigger-tree" / "config.sh"
    cfg.parent.mkdir()
    cfg.write_text("TT_LOG_PROMPTS='hash'\n")
    cfg.chmod(0)  # unreadable file: open() raises OSError
    try:
        mod = load_script("tt-log.py", tmp_path)
        cfg_out = mod.conf()
        assert cfg_out["TT_LOG_PROMPTS"] == "hash"  # unreadable override → safe default
        assert "agents" in cfg_out["TT_WATCH_REGEX"]  # plugin default file wins over DEFAULTS
    finally:
        cfg.chmod(0o644)


def test_conf_defaults_and_override(tmp_path):
    mod = load_script("tt-log.py", tmp_path)
    assert mod.conf()["TT_LOG_PROMPTS"] == "hash"
    (tmp_path / ".trigger-tree").mkdir()
    (tmp_path / ".trigger-tree" / "config.sh").write_text("TT_LOG_PROMPTS='off'\n")
    cfg = mod.conf()
    assert cfg["TT_LOG_PROMPTS"] == "off"
    assert cfg["TT_ROTATE_BYTES"] == "5242880"  # unset keys keep defaults


def test_session_event_and_bad_stdin(tmp_path, monkeypatch):
    mod = load_script("tt-log.py", tmp_path)
    run_main(mod, monkeypatch, ["session"], "not-json")
    assert read_history(tmp_path)[0] == {
        "schema_version": 1,
        "t": "session",
        "ts": read_history(tmp_path)[0]["ts"],
        "session": "?",
        "source": "unknown",
        "git_head": None,
    }


def test_session_configures_runtime_shell_capture(tmp_path, monkeypatch):
    env_file = tmp_path / "claude-env.sh"
    monkeypatch.setenv("CLAUDE_ENV_FILE", str(env_file))
    mod = load_script("tt-log.py", tmp_path)
    run_main(mod, monkeypatch, ["session"], json.dumps({"session_id": "S"}))

    configured = env_file.read_text()
    assert "export TT_RUNTIME_BASH_READS=1" in configured
    assert "export TT_SHELL_SESSION=S" in configured
    assert "tt-shell-capture.sh" in configured


@pytest.mark.parametrize("shell", ["bash", "zsh"])
def test_runtime_shell_capture_sources_safely_with_reader_alias(shell):
    executable = shutil.which(shell)
    if not executable:
        pytest.skip(f"{shell} is unavailable")
    capture = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "scripts", "tt-shell-capture.sh"
    )
    source = shlex.quote(capture)
    if shell == "bash":
        args = [executable, "-O", "expand_aliases", "-c", f"alias cat='cat -n'; source {source}"]
    else:
        args = [executable, "-c", f"alias cat='cat -n'; source {source}"]
    result = subprocess.run(args, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_session_capture_setup_failure_never_breaks_logging(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_ENV_FILE", str(tmp_path))  # a directory cannot be appended
    mod = load_script("tt-log.py", tmp_path)
    run_main(mod, monkeypatch, ["session"], json.dumps({"session_id": "S"}))
    assert read_history(tmp_path)[0]["t"] == "session"


def test_session_boundary_and_subagent_identity_are_preserved(tmp_path, monkeypatch):
    mod = load_script("tt-log.py", tmp_path)
    run_main(
        mod,
        monkeypatch,
        ["session"],
        json.dumps({"session_id": "S", "source": "compact"}),
    )
    run_main(
        mod,
        monkeypatch,
        ["read"],
        json.dumps(
            {
                "session_id": "S",
                "agent_id": "agent-123",
                "agent_type": "Explore",
                "tool_use_id": "toolu-read-1",
                "tool_name": "Read",
                "tool_input": {"file_path": str(tmp_path / "docs" / "a.md")},
            }
        ),
    )
    session, read = read_history(tmp_path)
    assert session["source"] == "compact"
    assert read["agent"] == "Explore"
    assert read["agent_id"] == "agent-123"
    assert read["tool_use_id"] == "toolu-read-1"


def test_read_scan_and_filtering(tmp_path, monkeypatch):
    mod = load_script("tt-log.py", tmp_path)
    watched = json.dumps(
        {
            "session_id": "S",
            "tool_name": "Read",
            "tool_input": {"file_path": str(tmp_path / "docs" / "a.md")},
        }
    )
    unwatched = json.dumps(
        {
            "session_id": "S",
            "tool_name": "Read",
            "tool_input": {"file_path": str(tmp_path / "src" / "a.py")},
        }
    )
    scan = json.dumps(
        {"session_id": "S", "tool_name": "Grep", "tool_input": {"path": str(tmp_path / "docs")}}
    )
    no_target = json.dumps({"session_id": "S", "tool_name": "Read", "tool_input": {}})
    for payload in (watched, unwatched, scan, no_target):
        run_main(mod, monkeypatch, ["read"], payload)
    events = read_history(tmp_path)
    assert [(e["t"], e["path"]) for e in events] == [("read", "docs/a.md"), ("scan", "docs")]
    assert events[0]["agent"] == "main"


def test_bash_doc_searches_are_scans_without_becoming_reads(tmp_path, monkeypatch):
    docs = tmp_path / "docs" / "ui"
    docs.mkdir(parents=True)
    (docs / "empty-states.md").write_text("x")
    (docs / "tables.md").write_text("x")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("x")
    mod = load_script("tt-log.py", tmp_path)
    docs_arg = docs.as_posix()
    empty_arg = (docs / "empty-states.md").as_posix()
    tables_arg = (docs / "tables.md").as_posix()

    commands = [
        f'rg -il "empty.state|empty_state" "{docs_arg}" | sort',
        f"rg -in empty_state '{empty_arg}' '{tables_arg}' | head -40",
        f"grep -R empty {docs_arg} && find {docs_arg} -name '*.md'",
        f"rg pattern {(tmp_path / 'src').as_posix()}",  # not a watched doc path
        "echo 'rg docs/ui'",  # text is not an executed search command
        "rg pattern nowhere/docs",  # nonexistent target: do not guess
        "rg 'unterminated",  # malformed shell: ignored safely
    ]
    for command in commands:
        payload = json.dumps(
            {
                "session_id": "S",
                "agent_type": "Explore",
                "tool_name": "Bash",
                "tool_input": {"command": command},
            }
        )
        run_main(mod, monkeypatch, ["bash"], payload)

    events = read_history(tmp_path)
    assert len(events) == 3  # one scan per distinct target per Bash invocation
    assert all(event["t"] == "scan" and event["tool"] == "Bash" for event in events)
    assert all(event["path"] == "docs/ui" and event["agent"] == "Explore" for event in events)


def test_bash_reader_commands_log_watched_files_as_reads(tmp_path, monkeypatch):
    docs = tmp_path / "docs"
    docs.mkdir()
    first = docs / "first.md"
    second = docs / "second.md"
    first.write_text("first")
    second.write_text("second")
    source = tmp_path / "app.py"
    source.write_text("print('ignored')")
    mod = load_script("tt-log.py", tmp_path)
    commands = [
        f"cat '{first}' '{second}'",
        f"head -20 '{first}'",
        f"tail -5 '{second}'",
        f"sed -n '1,20p' '{first}'",
        f"awk 'NR < 3' '{second}'",
        f"Get-Content -Path '{first}'",
        f"gc '{second}'",
        f"type '{first}'",
        f"cat '{source}'",
        f"sed -i 's/first/changed/' '{first}'",
        f"sed --in-place=.bak 's/second/changed/' '{second}'",
    ]

    for command in commands:
        payload = json.dumps(
            {
                "session_id": "S",
                "agent_type": "Explore",
                "tool_use_id": command,
                "tool_name": "Bash",
                "tool_input": {"command": command},
            }
        )
        run_main(mod, monkeypatch, ["bash"], payload)

    events = read_history(tmp_path)
    assert [event["path"] for event in events] == [
        "docs/first.md",
        "docs/second.md",
        "docs/first.md",
        "docs/second.md",
        "docs/first.md",
        "docs/second.md",
        "docs/first.md",
        "docs/second.md",
        "docs/first.md",
    ]
    assert all(
        event["t"] == "read" and event["tool"] == "Bash" and event["agent"] == "Explore"
        for event in events
    )


@pytest.mark.parametrize("shell_name", ["bash", "zsh"])
def test_runtime_capture_resolves_variables_command_substitution_and_loops(
    tmp_path, monkeypatch, shell_name
):
    shell = shutil.which(shell_name)
    if not shell:
        pytest.skip(f"{shell_name} is unavailable")
    docs = tmp_path / "docs" / "backlog"
    docs.mkdir(parents=True)
    first = docs / "0086-first.md"
    second = docs / "0087-second.md"
    first.write_text("first\n")
    second.write_text("second\n")
    env_file = tmp_path / "claude-env.sh"
    monkeypatch.setenv("CLAUDE_ENV_FILE", str(env_file))
    mod = load_script("tt-log.py", tmp_path)
    run_main(mod, monkeypatch, ["session"], json.dumps({"session_id": "S"}))

    command = f"""
source {shlex.quote(str(env_file))}
PICK=$(find docs/backlog -name '*.md' | sort | head -1)
cat "$PICK"
for DOC in {shlex.quote(str(first))} {shlex.quote(str(second))}; do
  head -1 "$DOC" >/dev/null
done
"""
    result = subprocess.run(
        [shell, "-c", command],
        cwd=tmp_path,
        env=dict(os.environ, CLAUDE_PROJECT_DIR=str(tmp_path)),
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout == "first\n"

    reads = [event for event in read_history(tmp_path) if event["t"] == "read"]
    assert [event["path"] for event in reads] == [
        "docs/backlog/0086-first.md",
        "docs/backlog/0086-first.md",
        "docs/backlog/0087-second.md",
    ]
    assert all(
        event["tool"] == "Bash"
        and event["agent"] == "runtime"
        and event["capture"] == "expanded-argv"
        for event in reads
    )

    monkeypatch.setenv("TT_RUNTIME_BASH_READS", "1")
    payload = json.dumps(
        {
            "session_id": "S",
            "tool_name": "Bash",
            "tool_input": {"command": f"cat '{first}'"},
        }
    )
    run_main(mod, monkeypatch, ["bash"], payload)
    assert len([event for event in read_history(tmp_path) if event["t"] == "read"]) == 3


def test_shell_read_event_filters_invalid_inputs_and_records_docs(tmp_path, monkeypatch):
    docs = tmp_path / "docs"
    docs.mkdir()
    target = docs / "a.md"
    target.write_text("a")
    source = tmp_path / "a.py"
    source.write_text("a")
    monkeypatch.setenv("TT_SHELL_SESSION", "S")
    mod = load_script("tt-log.py", tmp_path)

    run_main(mod, monkeypatch, ["shell-read"])
    run_main(mod, monkeypatch, ["shell-read", "printf", str(target)])
    run_main(mod, monkeypatch, ["shell-read", "cat", str(source)])
    run_main(mod, monkeypatch, ["shell-read", "sed", "-i", "s/a/b/", str(target)])
    assert read_history(tmp_path) == []

    run_main(mod, monkeypatch, ["shell-read", "cat", str(target)])
    assert read_history(tmp_path)[0] == {
        "schema_version": 1,
        "t": "read",
        "ts": read_history(tmp_path)[0]["ts"],
        "session": "S",
        "tool": "Bash",
        "path": "docs/a.md",
        "agent": "runtime",
        "capture": "expanded-argv",
    }


def test_shell_parser_and_bash_without_command(tmp_path, monkeypatch):
    mod = load_script("tt-log.py", tmp_path)
    assert mod.shell_segments("cd docs && rg x . | sort; echo done") == [
        ["cd", "docs"],
        ["rg", "x", "."],
        ["sort"],
        ["echo", "done"],
    ]
    assert mod.shell_segments("echo 'unterminated") == []
    run_main(mod, monkeypatch, ["bash"], json.dumps({"tool_name": "Bash", "tool_input": {}}))
    assert read_history(tmp_path) == []


def test_prompt_modes(tmp_path, monkeypatch):
    conf_dir = tmp_path / ".trigger-tree"
    conf_dir.mkdir()
    payload = json.dumps({"session_id": "S", "prompt": "secret plans\nline two"})

    mod = load_script("tt-log.py", tmp_path)
    run_main(mod, monkeypatch, ["prompt"], payload)
    entry = read_history(tmp_path)[-1]
    assert "prompt_hash" in entry and "secret" not in json.dumps(entry)

    (conf_dir / "config.sh").write_text("TT_LOG_PROMPTS='truncate'\n")
    run_main(mod, monkeypatch, ["prompt"], payload)
    assert read_history(tmp_path)[-1]["prompt"] == "secret plans line two"

    (conf_dir / "config.sh").write_text("TT_LOG_PROMPTS='off'\n")
    run_main(mod, monkeypatch, ["prompt"], payload)
    entry = read_history(tmp_path)[-1]
    assert entry["t"] == "prompt" and "prompt" not in entry and "prompt_hash" not in entry


def test_skill_event(tmp_path, monkeypatch):
    mod = load_script("tt-log.py", tmp_path)
    run_main(
        mod,
        monkeypatch,
        ["skill"],
        json.dumps({"session_id": "S", "tool_name": "Skill", "tool_input": {"skill": "deploy"}}),
    )
    run_main(
        mod,
        monkeypatch,
        ["skill"],
        json.dumps({"session_id": "S", "tool_name": "Skill", "tool_input": {}}),
    )  # nameless: ignored
    events = read_history(tmp_path)
    assert len(events) == 1 and events[0]["skill"] == "deploy"


def test_note_uses_session_env(tmp_path, monkeypatch):
    mod = load_script("tt-log.py", tmp_path)
    monkeypatch.setenv("CLAUDE_SESSION_ID", "sess-env")
    monkeypatch.setattr(sys, "argv", ["tt-log.py", "note", "router", "tweak"])
    mod.main()
    entry = read_history(tmp_path)[0]
    assert entry == {
        "schema_version": 1,
        "t": "note",
        "ts": entry["ts"],
        "session": "sess-env",
        "text": "router tweak",
    }
    # empty note text writes nothing
    monkeypatch.setattr(sys, "argv", ["tt-log.py", "note"])
    mod.main()
    assert len(read_history(tmp_path)) == 1


def test_ingest_external_events(tmp_path, monkeypatch):
    mod = load_script("tt-log.py", tmp_path)
    monkeypatch.setenv("CLAUDE_SESSION_ID", "codex-1")

    def ingest(payload):
        monkeypatch.setattr(sys, "argv", ["tt-log.py", "ingest", payload])
        mod.main()

    ingest('{"t":"read","path":"docs/a.md"}')
    entry = read_history(tmp_path)[0]
    assert entry["t"] == "read" and entry["path"] == "docs/a.md"
    assert entry["session"] == "codex-1" and entry["agent"] == "external" and entry["ts"]

    ingest('{"t":"scan"}')  # scan without path: dropped
    ingest('{"t":"bogus","x":1}')  # unknown type: dropped
    ingest("not-json")  # invalid json: dropped
    monkeypatch.setattr(sys, "argv", ["tt-log.py", "ingest"])
    mod.main()  # missing payload: dropped
    assert len(read_history(tmp_path)) == 1

    ingest('{"t":"note","text":"from codex","ts":"2026-07-01T00:00:00Z"}')
    entry = read_history(tmp_path)[-1]
    assert entry["text"] == "from codex" and entry["ts"] == "2026-07-01T00:00:00Z"


def test_rotation(tmp_path, monkeypatch):
    (tmp_path / ".trigger-tree").mkdir()
    (tmp_path / ".trigger-tree" / "config.sh").write_text("TT_ROTATE_BYTES='10'\n")
    mod = load_script("tt-log.py", tmp_path)
    for _ in range(2):
        run_main(mod, monkeypatch, ["session"], json.dumps({"session_id": "S"}))
    files = os.listdir(tmp_path / ".trigger-tree")
    assert any(f.startswith("history-") for f in files), files
    assert "history.jsonl" in files


def test_rotation_never_overwrites_same_second_archive(tmp_path, monkeypatch):
    history = tmp_path / ".trigger-tree"
    history.mkdir()
    (history / "history.jsonl").write_text("x" * 20)
    (history / "history-20260719-120000.jsonl").write_text("original")
    mod = load_script("tt-log.py", tmp_path)
    monkeypatch.setattr(mod.time, "strftime", lambda *_args, **_kwargs: "20260719-120000")
    mod.append({"t": "session"}, 10)
    assert (history / "history-20260719-120000.jsonl").read_text() == "original"
    assert (history / "history-20260719-120000-1.jsonl").read_text() == "x" * 20


def test_local_outcome_signals_and_test_command_detection(tmp_path, monkeypatch):
    mod = load_script("tt-log.py", tmp_path)
    assert mod.looks_like_test_command("pytest -q")
    assert mod.looks_like_test_command("npm test && echo done")
    assert mod.looks_like_test_command("cargo test")
    assert mod.looks_like_test_command("mix test")
    assert not mod.looks_like_test_command("echo pytest")
    assert not mod.looks_like_test_command("")

    heads = iter(["before", "after"])
    monkeypatch.setattr(mod, "git_head", lambda: next(heads))
    run_main(mod, monkeypatch, ["session"], json.dumps({"session_id": "S", "source": "startup"}))
    run_main(
        mod,
        monkeypatch,
        ["bash"],
        json.dumps({"session_id": "S", "tool_input": {"command": "pytest -q"}}),
    )
    run_main(
        mod,
        monkeypatch,
        ["outcome"],
        json.dumps({"session_id": "S", "reason": "prompt_input_exit"}),
    )
    events = read_history(tmp_path)
    assert events[-2]["t"] == "test" and events[-2]["status"] == "pass"
    assert events[-1]["t"] == "outcome"
    assert events[-1]["git_commit_landed"] is True
    assert events[-1]["test_status"] == "pass"
    assert events[-1]["source"] == "prompt_input_exit"


def test_failed_test_signal_and_git_head_failure(tmp_path, monkeypatch):
    mod = load_script("tt-log.py", tmp_path)
    monkeypatch.setattr(
        mod.subprocess, "run", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError())
    )
    assert mod.git_head() is None
    run_main(
        mod,
        monkeypatch,
        ["bash-failure"],
        json.dumps({"session_id": "S", "tool_input": {"command": "go test ./..."}}),
    )
    assert read_history(tmp_path)[-1]["status"] == "fail"
    assert mod.session_signals("missing") == (None, None)
    monkeypatch.setattr(mod.glob, "glob", lambda _pattern: [str(tmp_path / "missing.jsonl")])
    assert mod.session_signals("missing") == (None, None)
    corrupt = tmp_path / "corrupt.jsonl"
    corrupt.write_text("{torn\n")
    monkeypatch.setattr(mod.glob, "glob", lambda _pattern: [str(corrupt)])
    assert mod.session_signals("missing") == (None, None)
