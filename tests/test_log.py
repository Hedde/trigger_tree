import io
import json
import os
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
        "t": "session",
        "ts": read_history(tmp_path)[0]["ts"],
        "session": "?",
        "source": "unknown",
    }


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
    assert entry == {"t": "note", "ts": entry["ts"], "session": "sess-env", "text": "router tweak"}
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
