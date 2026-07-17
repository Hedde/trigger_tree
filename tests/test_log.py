import io
import json
import os
import sys

from conftest import load_script


def run_main(mod, monkeypatch, argv, stdin_text="{}"):
    monkeypatch.setattr(sys, "argv", ["tt-log.py"] + argv)
    monkeypatch.setattr(sys, "stdin", io.StringIO(stdin_text))
    mod.main()


def read_history(project):
    path = os.path.join(project, ".trigger-tree", "history.jsonl")
    return [json.loads(l) for l in open(path)] if os.path.isfile(path) else []


def test_rel_path(tmp_path):
    mod = load_script("tt-log.py", tmp_path)
    assert mod.rel_path(str(tmp_path / "docs" / "a.md")) == "docs/a.md"
    assert mod.rel_path("/elsewhere/x.md") == "/elsewhere/x.md"


def test_conf_defaults_and_override(tmp_path):
    mod = load_script("tt-log.py", tmp_path)
    assert mod.conf()["TT_LOG_PROMPTS"] == "truncate"
    (tmp_path / ".trigger-tree").mkdir()
    (tmp_path / ".trigger-tree" / "config.sh").write_text("TT_LOG_PROMPTS='off'\n")
    cfg = mod.conf()
    assert cfg["TT_LOG_PROMPTS"] == "off"
    assert cfg["TT_ROTATE_BYTES"] == "5242880"  # unset keys keep defaults


def test_session_event_and_bad_stdin(tmp_path, monkeypatch):
    mod = load_script("tt-log.py", tmp_path)
    run_main(mod, monkeypatch, ["session"], "not-json")
    assert read_history(tmp_path)[0] == {
        "t": "session", "ts": read_history(tmp_path)[0]["ts"], "session": "?"}


def test_read_scan_and_filtering(tmp_path, monkeypatch):
    mod = load_script("tt-log.py", tmp_path)
    watched = json.dumps({"session_id": "S", "tool_name": "Read",
                          "tool_input": {"file_path": str(tmp_path / "docs" / "a.md")}})
    unwatched = json.dumps({"session_id": "S", "tool_name": "Read",
                            "tool_input": {"file_path": str(tmp_path / "src" / "a.py")}})
    scan = json.dumps({"session_id": "S", "tool_name": "Grep",
                       "tool_input": {"path": str(tmp_path / "docs")}})
    no_target = json.dumps({"session_id": "S", "tool_name": "Read", "tool_input": {}})
    for payload in (watched, unwatched, scan, no_target):
        run_main(mod, monkeypatch, ["read"], payload)
    events = read_history(tmp_path)
    assert [(e["t"], e["path"]) for e in events] == [("read", "docs/a.md"), ("scan", "docs")]
    assert events[0]["agent"] == "main"


def test_prompt_modes(tmp_path, monkeypatch):
    conf_dir = tmp_path / ".trigger-tree"
    conf_dir.mkdir()
    payload = json.dumps({"session_id": "S", "prompt": "secret plans\nline two"})

    mod = load_script("tt-log.py", tmp_path)
    run_main(mod, monkeypatch, ["prompt"], payload)
    assert read_history(tmp_path)[-1]["prompt"] == "secret plans line two"

    (conf_dir / "config.sh").write_text("TT_LOG_PROMPTS='hash'\n")
    run_main(mod, monkeypatch, ["prompt"], payload)
    entry = read_history(tmp_path)[-1]
    assert "prompt_hash" in entry and "secret" not in json.dumps(entry)

    (conf_dir / "config.sh").write_text("TT_LOG_PROMPTS='off'\n")
    run_main(mod, monkeypatch, ["prompt"], payload)
    entry = read_history(tmp_path)[-1]
    assert entry["t"] == "prompt" and "prompt" not in entry and "prompt_hash" not in entry


def test_skill_event(tmp_path, monkeypatch):
    mod = load_script("tt-log.py", tmp_path)
    run_main(mod, monkeypatch, ["skill"], json.dumps(
        {"session_id": "S", "tool_name": "Skill", "tool_input": {"skill": "deploy"}}))
    run_main(mod, monkeypatch, ["skill"], json.dumps(
        {"session_id": "S", "tool_name": "Skill", "tool_input": {}}))  # nameless: ignored
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


def test_rotation(tmp_path, monkeypatch):
    (tmp_path / ".trigger-tree").mkdir()
    (tmp_path / ".trigger-tree" / "config.sh").write_text("TT_ROTATE_BYTES='10'\n")
    mod = load_script("tt-log.py", tmp_path)
    for _ in range(2):
        run_main(mod, monkeypatch, ["session"], json.dumps({"session_id": "S"}))
    files = os.listdir(tmp_path / ".trigger-tree")
    assert any(f.startswith("history-") for f in files), files
    assert "history.jsonl" in files
