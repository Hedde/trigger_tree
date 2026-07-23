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
    assert out.count("✓") == 9
    assert "1 usable events, latest 2026-07-17T10:00:00Z" in out
    assert "prompt logging: hash (set by the plugin default)" in out
    assert "Python:" not in out  # the label stays lowercase; paths may contain Python
    assert "all checks passed" in out


def test_doctor_warns_before_first_event_and_without_statusline(tmp_path, capsys):
    (tmp_path / ".gitignore").write_text(".trigger-tree/*\n")
    mod = load_script("tt-doctor.py", tmp_path)
    assert mod.main() == 0
    out = capsys.readouterr().out
    assert out.count("!") == 3
    assert "telemetry healthy — 3 optional setup warnings" in out


def test_doctor_fails_actionably_on_broken_project(tmp_path, monkeypatch, capsys):
    (tmp_path / ".trigger-tree").mkdir()
    (tmp_path / ".trigger-tree" / "history.jsonl").write_text("bad\n")
    mod = load_script("tt-doctor.py", tmp_path)
    monkeypatch.setattr(mod, "PLUGIN_ROOT", str(tmp_path))
    assert mod.main() == 1
    out = capsys.readouterr().out
    assert out.count("✗") == 3
    assert "run /tt setup" in out and "reinstall the plugin" in out
    assert "attention needed — 3 failed, 2 warnings" in out


def test_doctor_liveness_distinguishes_current_missing_recent_and_stale(tmp_path, monkeypatch):
    history = tmp_path / ".trigger-tree"
    history.mkdir()
    log = history / "history.jsonl"
    log.write_text(
        '{"schema_version":1,"t":"session","session":"CURRENT","ts":"2026-07-22T10:00:00Z"}\n'
    )
    mod = load_script("tt-doctor.py", tmp_path)
    monkeypatch.setenv("CLAUDE_SESSION_ID", "CURRENT")
    assert mod.liveness_health()[0] == "PASS"
    monkeypatch.setenv("CLAUDE_SESSION_ID", "MISSING")
    state, message = mod.liveness_health()
    assert (
        state == "FAIL" and "/hooks" in message and "restart" in message and "reinstall" in message
    )
    monkeypatch.delenv("CLAUDE_SESSION_ID")
    monkeypatch.setattr(mod.time, "time", lambda: 2_000_000_000)
    state, message = mod.liveness_health()
    assert state == "WARN" and "stale" in message and "informational" in message


def test_doctor_liveness_accepts_recent_session_state_without_history(tmp_path, monkeypatch):
    sessions = tmp_path / ".trigger-tree" / "sessions"
    sessions.mkdir(parents=True)
    state_file = sessions / "state.json"
    state_file.write_text("{}")
    mod = load_script("tt-doctor.py", tmp_path)
    monkeypatch.setattr(mod.time, "time", lambda: state_file.stat().st_mtime)
    assert mod.liveness_health() == ("PASS", "hook liveness: recent session/read activity found")


def test_doctor_coverage_reports_zero_low_and_healthy(tmp_path):
    (tmp_path / "README.md").write_text("root")
    mod = load_script("tt-doctor.py", tmp_path)
    state, message = mod.coverage_health()
    assert state == "FAIL" and "TT_WATCH_REGEX" in message and ".trigger-tree/config.sh" in message

    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "watched.md").write_text("watched")
    for name in ("ONE.md", "TWO.md", "THREE.md"):
        (tmp_path / name).write_text(name)
    assert mod.coverage_health()[0] == "WARN"
    for name in ("ONE.md", "TWO.md", "THREE.md", "README.md"):
        (tmp_path / name).unlink()
    assert mod.coverage_health()[0] == "PASS"


def test_liveness_skips_disappearing_history_and_invalid_timestamps(tmp_path, monkeypatch):
    telemetry = tmp_path / ".trigger-tree"
    telemetry.mkdir()
    history = telemetry / "history.jsonl"
    history.write_text('{"t":"session","ts":null}\n')
    mod = load_script("tt-doctor.py", tmp_path)
    assert mod.liveness_health()[0] == "WARN"
    monkeypatch.setattr(mod.glob, "glob", lambda _pattern: [str(tmp_path / "gone.jsonl")])
    assert mod._lifecycle_events() == []


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
    state, message = mod.python_health()
    assert state == "FAIL"
    assert "python: 3.9 unsupported" in message and "3.10–3.14" in message
    assert mod.sys.executable in message


def test_coverage_health_respects_acknowledged_scope(tmp_path, monkeypatch):
    mod = load_script("tt-doctor.py", tmp_path)
    monkeypatch.setattr(mod, "ROOT", str(tmp_path))
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.md").write_text("doc")
    (tmp_path / "CHANGELOG.md").write_text("log")
    (tmp_path / ".trigger-tree").mkdir()
    (tmp_path / ".trigger-tree" / "config.sh").write_text("TT_SCOPE_IGNORE='CHANGELOG.md'\n")
    assert mod.scope_ignore() == ("CHANGELOG.md",)
    state, message = mod.coverage_health()
    assert "1 of 1 markdown files watched" in message
    monkeypatch.setattr(mod, "ROOT", str(tmp_path / "leeg"))
    assert mod.scope_ignore() == ()  # valt terug op de lege plugin-default


def codex_config(tmp_path, monkeypatch, body):
    home = tmp_path / "codex-home"
    home.mkdir(exist_ok=True)
    (home / "config.toml").write_text(body, encoding="utf-8")
    monkeypatch.setenv("CODEX_HOME", str(home))


def trust_entry(event):
    return f'[hooks.state."trigger-tree@trigger-tree:hooks/hooks.json:{event}:0:0"]\ntrusted_hash = "sha256:abc"\n'


def test_codex_trust_is_skipped_without_codex_or_without_the_plugin(tmp_path, monkeypatch):
    mod = load_script("tt-doctor.py", tmp_path)
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "nergens"))
    assert mod.codex_trust_health() is None
    codex_config(tmp_path, monkeypatch, '[projects."/x"]\ntrust_level = "trusted"\n')
    assert mod.codex_trust_health() is None  # plugin niet geïnstalleerd
    codex_config(tmp_path, monkeypatch, '[plugins."trigger-tree@trigger-tree"]\nenabled = false\n')
    assert mod.codex_trust_health() is None  # plugin uitgeschakeld


def test_codex_trust_warns_until_all_hooks_are_trusted(tmp_path, monkeypatch):
    mod = load_script("tt-doctor.py", tmp_path)
    enabled = '[plugins."trigger-tree@trigger-tree"]\nenabled = true\n'
    codex_config(tmp_path, monkeypatch, enabled)
    state, message = mod.codex_trust_health()
    assert state == "WARN"
    assert "Trust all and continue" in message
    assert "non-interactive codex exec never persists trust" in message
    codex_config(tmp_path, monkeypatch, enabled + trust_entry("session_start"))
    state, message = mod.codex_trust_health()
    assert state == "WARN"
    assert "1 of 4 hooks trusted" in message
    assert "post_tool_use" in message and "stop" in message and "user_prompt_submit" in message
    all_four = enabled + "".join(
        trust_entry(event)
        for event in ("session_start", "user_prompt_submit", "post_tool_use", "stop")
    )
    codex_config(tmp_path, monkeypatch, all_four)
    state, message = mod.codex_trust_health()
    assert state == "PASS"
    assert "all 4 hooks have a persisted trust decision" in message


def test_doctor_output_includes_codex_trust_when_state_is_available(tmp_path, monkeypatch, capsys):
    wire_project(tmp_path)
    mod = load_script("tt-doctor.py", tmp_path)
    codex_config(tmp_path, monkeypatch, '[plugins."trigger-tree@trigger-tree"]\nenabled = true\n')
    assert mod.main() == 0
    out = capsys.readouterr().out
    assert "! codex trust: hooks are installed but not trusted" in out


def test_prompts_health_reports_the_selecting_layer_and_rejects_invalid(tmp_path, monkeypatch):
    mod = load_script("tt-doctor.py", tmp_path)
    # Zonder leesbare lagen geldt de ingebouwde fallback.
    monkeypatch.setattr(mod, "PLUGIN_ROOT", str(tmp_path / "nergens"))
    state, message = mod.prompts_health()
    assert state == "PASS" and "hash (set by the built-in fallback)" in message
    user_config = tmp_path / "user-config.sh"
    user_config.write_text("TT_LOG_PROMPTS='off'\n")
    monkeypatch.setenv("TT_USER_CONFIG", str(user_config))
    state, message = mod.prompts_health()
    assert state == "PASS" and "off (set by the user default)" in message
    (tmp_path / ".trigger-tree").mkdir()
    (tmp_path / ".trigger-tree" / "config.sh").write_text("TT_LOG_PROMPTS='truncate'\n")
    state, message = mod.prompts_health()
    assert state == "PASS" and "truncate (set by the project override)" in message
    (tmp_path / ".trigger-tree" / "config.sh").write_text("TT_LOG_PROMPTS='alles'\n")
    state, message = mod.prompts_health()
    assert state == "FAIL" and "invalid mode 'alles' from the project override" in message
