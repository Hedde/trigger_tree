import json

from conftest import load_script


def wire_project(project, events=True):
    (project / ".claude").mkdir()
    (project / ".claude" / "tt-statusline.py").write_text("# installed\n")
    (project / ".claude" / "settings.json").write_text(
        json.dumps({"statusLine": {"command": "python3 .claude/tt-statusline.py"}})
    )
    (project / ".gitignore").write_text(".trigger-tree/\n")
    if events:
        (project / ".trigger-tree").mkdir()
        (project / ".trigger-tree" / "history.jsonl").write_text(
            '{"schema_version":1,"t":"session","ts":"2026-07-17T10:00:00Z"}\n'
        )


def test_doctor_all_checks_pass(tmp_path, capsys):
    wire_project(tmp_path)
    mod = load_script("tt-doctor.py", tmp_path)
    assert mod.main() == 0
    out = capsys.readouterr().out
    assert out.count("✓") == 6
    assert "1 usable events, latest 2026-07-17T10:00:00Z" in out
    assert "Python" not in out  # message uses stable lowercase wording
    assert "all checks passed" in out


def test_doctor_warns_before_first_event_and_without_statusline(tmp_path, capsys):
    (tmp_path / ".gitignore").write_text(".trigger-tree/*\n")
    mod = load_script("tt-doctor.py", tmp_path)
    assert mod.main() == 0
    out = capsys.readouterr().out
    assert out.count("!") == 2
    assert "telemetry healthy — 2 optional setup warnings" in out


def test_doctor_fails_actionably_on_broken_project(tmp_path, monkeypatch, capsys):
    (tmp_path / ".trigger-tree").mkdir()
    (tmp_path / ".trigger-tree" / "history.jsonl").write_text("bad\n")
    mod = load_script("tt-doctor.py", tmp_path)
    monkeypatch.setattr(mod, "PLUGIN_ROOT", str(tmp_path))
    assert mod.main() == 1
    out = capsys.readouterr().out
    assert out.count("✗") == 3
    assert "run /tt setup" in out and "reinstall the plugin" in out
    assert "attention needed — 3 failed, 1 warnings" in out


def test_doctor_handles_unreadable_or_invalid_files(tmp_path, monkeypatch):
    mod = load_script("tt-doctor.py", tmp_path)
    assert mod.load_json(tmp_path / "missing") is None
    broken = tmp_path / "broken.json"
    broken.write_text("{")
    assert mod.load_json(broken) is None
    history = tmp_path / ".trigger-tree"
    history.mkdir()
    (history / "history.jsonl").write_text("{}\n")
    monkeypatch.setattr("builtins.open", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError()))
    assert mod.history_health() == ("FAIL", "telemetry: history exists but cannot be read")


def test_doctor_reports_rotated_legacy_and_corrupt_history(tmp_path):
    history = tmp_path / ".trigger-tree"
    history.mkdir()
    (history / "history-20260718-120000.jsonl").write_text(
        '{"t":"session","session":"legacy"}\n{torn\n[]\n'
    )
    (history / "history.jsonl").write_text(
        '{"schema_version":1,"t":"session","session":"current"}\n'
    )
    mod = load_script("tt-doctor.py", tmp_path)
    state, message = mod.history_health()
    assert state == "WARN"
    assert "1 rotated file(s) included" in message
    assert "1 legacy event(s) migrated" in message
    assert "2 corrupt line(s) ignored" in message


def test_doctor_rejects_future_history_schema(tmp_path):
    history = tmp_path / ".trigger-tree"
    history.mkdir()
    (history / "history.jsonl").write_text('{"schema_version":99,"t":"read"}\n')
    mod = load_script("tt-doctor.py", tmp_path)
    state, message = mod.history_health()
    assert state == "FAIL" and "newer schema" in message and "update trigger-tree" in message


def test_doctor_validates_config_values(tmp_path):
    config_dir = tmp_path / ".trigger-tree"
    config_dir.mkdir()
    config = config_dir / "config.sh"
    mod = load_script("tt-doctor.py", tmp_path)

    config.write_text("TT_LOG_PROMPTS='truncate'\nTT_ROTATE_BYTES='1024'\n")
    assert mod.config_health()[0] == "PASS"
    for value, expected in (
        ("TT_WATCH_REGEX='([broken'\n", "invalid"),
        ("TT_LOG_PROMPTS='plaintext'\n", "hash, truncate, or off"),
        ("TT_ROTATE_BYTES='0'\n", "positive integer"),
        ("TT_EXPERIMENTAL_OUTCOMES='maybe'\n", "must be on or off"),
        ("TT_ROTATE_BYTES=nope\n", "unparseable assignment"),
    ):
        config.write_text(value)
        state, message = mod.config_health()
        assert state == "FAIL" and expected in message


def test_doctor_reports_unreadable_config(tmp_path, monkeypatch):
    config_dir = tmp_path / ".trigger-tree"
    config_dir.mkdir()
    config = config_dir / "config.sh"
    config.write_text("TT_LOG_PROMPTS='hash'\n")
    mod = load_script("tt-doctor.py", tmp_path)
    real_open = open

    def fail_config(path, *args, **kwargs):
        if str(path) == str(config):
            raise OSError("permission denied")
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr("builtins.open", fail_config)
    assert mod.config_health() == (
        "FAIL",
        "config: project override cannot be read — fix permissions or remove it",
    )


def test_doctor_detects_python_version_drift(tmp_path, monkeypatch):
    mod = load_script("tt-doctor.py", tmp_path)
    monkeypatch.setattr(mod.sys, "version_info", (3, 9, 20))
    assert mod.python_health() == (
        "FAIL",
        "python: 3.9 unsupported — configure Python 3.10–3.13",
    )
