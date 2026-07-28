import json
from datetime import datetime, timezone

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


def test_doctor_all_checks_pass(tmp_path, monkeypatch, capsys):
    wire_project(tmp_path)
    mod = load_script("tt-doctor.py", tmp_path)
    monkeypatch.setattr(mod.time, "time", lambda: 1_784_282_400)
    assert mod.main() == 0
    out = capsys.readouterr().out
    assert out.count("✓") == 8
    assert out.count("!") == 2
    assert "1 usable events, latest 2026-07-17T10:00:00Z" in out
    assert "prompt logging: hash (set by the plugin default)" in out
    assert "task-cluster previews unavailable" in out
    assert "instructions: no manifest" in out
    assert "Python:" not in out  # the label stays lowercase; paths may contain Python
    assert "telemetry healthy — 2 optional setup warnings" in out


def test_doctor_warns_before_first_event_and_without_statusline(tmp_path, capsys):
    (tmp_path / ".gitignore").write_text(".trigger-tree/*\n")
    mod = load_script("tt-doctor.py", tmp_path)
    assert mod.main() == 0
    out = capsys.readouterr().out
    assert out.count("!") == 5
    assert "telemetry healthy — 5 optional setup warnings" in out


def test_doctor_fails_actionably_on_broken_project(tmp_path, monkeypatch, capsys):
    (tmp_path / ".trigger-tree").mkdir()
    (tmp_path / ".trigger-tree" / "history.jsonl").write_text("bad\n")
    mod = load_script("tt-doctor.py", tmp_path)
    monkeypatch.setattr(mod, "PLUGIN_ROOT", str(tmp_path))
    assert mod.main() == 1
    out = capsys.readouterr().out
    assert out.count("✗") == 3
    assert "run /tt setup" in out and "reinstall the plugin" in out
    assert "attention needed — 3 failed, 4 warnings" in out


def test_doctor_liveness_distinguishes_current_missing_recent_and_stale(tmp_path, monkeypatch):
    history = tmp_path / ".trigger-tree"
    history.mkdir()
    log = history / "history.jsonl"
    log.write_text(
        '{"schema_version":1,"t":"session","session":"CURRENT","ts":"2026-07-22T10:00:00Z"}\n'
    )
    mod = load_script("tt-doctor.py", tmp_path)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "CURRENT")
    assert mod.liveness_health()[0] == "PASS"
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "MISSING")
    state, message = mod.liveness_health()
    assert (
        state == "FAIL" and "/hooks" in message and "restart" in message and "reinstall" in message
    )
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID")
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
        ("TT_LOG_TOPICS='maybe'\n", "must be on or off"),
        ("TT_LOG_COMMANDS='raw'\n", "off, classified, or full"),
        ("TT_EDIT_REGEX='([broken'\n", "invalid"),
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
    assert state == "WARN" and "hash (set by the built-in fallback)" in message
    user_config = tmp_path / "user-config.sh"
    user_config.write_text("TT_LOG_PROMPTS='off'\n")
    monkeypatch.setenv("TT_USER_CONFIG", str(user_config))
    state, message = mod.prompts_health()
    assert state == "WARN" and "off (set by the user default)" in message
    (tmp_path / ".trigger-tree").mkdir()
    (tmp_path / ".trigger-tree" / "config.sh").write_text("TT_LOG_PROMPTS='truncate'\n")
    state, message = mod.prompts_health()
    assert state == "PASS" and "truncate (set by the project override)" in message
    (tmp_path / ".trigger-tree" / "config.sh").write_text("TT_LOG_PROMPTS='alles'\n")
    state, message = mod.prompts_health()
    assert state == "FAIL" and "invalid mode 'alles' from the project override" in message


def test_instructions_health_absent_invalid_stale_disabled_and_current(tmp_path):
    mod = load_script("tt-doctor.py", tmp_path)
    assert mod.instructions_health()[0] == "WARN"
    telemetry = tmp_path / ".trigger-tree"
    telemetry.mkdir()
    manifest = telemetry / "directives.json"
    manifest.write_text("{")
    assert mod.instructions_health()[0] == "FAIL"

    instruction = tmp_path / "CLAUDE.md"
    instruction.write_bytes(b"route design\n")
    import hashlib

    value = {
        "schema": 1,
        "instruction_files": [
            {"path": "CLAUDE.md", "sha256": hashlib.sha256(b"route design\n").hexdigest()}
        ],
        "directives": [
            {
                "id": "route-design",
                "source": {"file": "CLAUDE.md", "line": 1},
                "probe": {
                    "type": "route_followed",
                    "topics": ["design"],
                    "paths": ["docs/design.md"],
                },
            }
        ],
    }
    manifest.write_text(json.dumps(value))
    instruction.write_text("changed\n")
    assert "stale" in mod.instructions_health()[1]
    instruction.write_bytes(b"route design\n")
    # The routed doc does not exist yet, so the probe can never be satisfied.
    status, message = mod.instructions_health()
    assert status == "FAIL" and "can never fire" in message and "route-design" in message
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "design.md").write_text("design\n")
    assert "capture disabled" in mod.instructions_health()[1]
    (telemetry / "config.sh").write_text(
        "TT_LOG_TOPICS='on'\nTT_LOG_COMMANDS='classified'\nTT_EDIT_REGEX='^src/'\n"
    )
    assert mod.instructions_health() == (
        "PASS",
        "instructions: manifest current and configured probes are observable",
    )


def test_doctor_all_pass_summary_branch(tmp_path, monkeypatch, capsys):
    mod = load_script("tt-doctor.py", tmp_path)
    for name in (
        "hooks_health",
        "liveness_health",
        "codex_trust_health",
        "config_health",
        "prompts_health",
        "instructions_health",
        "coverage_health",
        "surfaces_health",
        "python_health",
        "ignore_health",
        "statusline_health",
        "history_health",
    ):
        monkeypatch.setattr(mod, name, lambda: ("PASS", "ok"))
    assert mod.main() == 0
    assert "all checks passed" in capsys.readouterr().out


def test_doctor_warns_on_watched_symlinked_surfaces(tmp_path, monkeypatch):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "linked").mkdir()
    mod = load_script("tt-doctor.py", tmp_path)
    assert mod.surfaces_health() is None  # zonder symlinks geen melding
    import os as osmod

    real_islink = osmod.path.islink
    monkeypatch.setattr(osmod.path, "islink", lambda p: str(p).endswith("linked") or real_islink(p))
    state, message = mod.surfaces_health()
    assert state == "WARN"
    assert "docs/linked" in message and "outside the inventory" in message


def test_liveness_reads_the_variable_claude_code_actually_exports(tmp_path, monkeypatch):
    """Regression for issue #21.

    Claude Code exports CLAUDE_CODE_SESSION_ID. CLAUDE_SESSION_ID is only a
    ${...} placeholder substituted into hook command strings, so reading it
    alone made the strict branch unreachable and doctor reported PASS in a
    project where the Claude hooks had never recorded anything.
    """
    mod = load_script("tt-doctor.py", tmp_path)
    telemetry = tmp_path / ".trigger-tree"
    telemetry.mkdir()
    (telemetry / "history.jsonl").write_text(
        json.dumps({"t": "session", "session": "LIVE", "ts": "2026-07-28T10:00:00Z"}) + "\n"
    )
    for name in ("CLAUDE_CODE_SESSION_ID", "CLAUDE_SESSION_ID", "TT_SESSION_ID"):
        monkeypatch.delenv(name, raising=False)

    # The real Claude Code variable must drive the strict branch.
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "LIVE")
    assert mod.liveness_health() == ("PASS", "hook liveness: current session start was recorded")
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "ABSENT")
    status, message = mod.liveness_health()
    assert status == "FAIL" and "current session start is absent" in message

    # The placeholder name stays supported for clients that do export it.
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID")
    monkeypatch.setenv("CLAUDE_SESSION_ID", "ABSENT")
    assert mod.liveness_health()[0] == "FAIL"


def test_session_id_prefers_claude_code_over_the_placeholder(monkeypatch):
    import tt_runtime

    for name in ("CLAUDE_CODE_SESSION_ID", "CLAUDE_SESSION_ID", "TT_SESSION_ID"):
        monkeypatch.delenv(name, raising=False)
    assert tt_runtime.session_id() is None
    monkeypatch.setenv("TT_SESSION_ID", "explicit")
    assert tt_runtime.session_id() == "explicit"
    monkeypatch.setenv("CLAUDE_SESSION_ID", "placeholder")
    assert tt_runtime.session_id() == "placeholder"
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "real")
    assert tt_runtime.session_id() == "real"


def test_liveness_names_the_clients_that_have_written(tmp_path, monkeypatch):
    """Issue #21: another client's telemetry must not read as your client working."""
    mod = load_script("tt-doctor.py", tmp_path)
    telemetry = tmp_path / ".trigger-tree"
    telemetry.mkdir()
    telemetry.joinpath("history.jsonl").write_text(
        "\n".join(
            json.dumps(event)
            for event in (
                {"t": "session", "session": "c1", "ts": "2026-07-20T09:00:00Z", "client": "codex"},
                {"t": "read", "session": "c1", "ts": "2026-07-28T09:00:00Z", "client": "codex"},
                {"t": "session", "session": "x", "ts": "2026-07-01T09:00:00Z", "client": 7},
                {"t": "session", "session": "y", "ts": None, "client": "gemini"},
            )
        )
        + "\n"
    )
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "LIVE")
    status, message = mod.liveness_health()
    assert status == "FAIL"
    assert "recorded clients: codex 2026-07-28, gemini unknown date" in message
    assert "client 7" not in message

    telemetry.joinpath("history.jsonl").write_text(
        json.dumps({"t": "session", "session": "s", "ts": "2026-07-28T09:00:00Z"}) + "\n"
    )
    assert "recorded clients" not in mod.liveness_health()[1]


def test_liveness_names_clients_on_the_branch_codex_actually_reaches(tmp_path, monkeypatch):
    """Codex exports no session id, so the lenient branch is all it ever reaches."""
    mod = load_script("tt-doctor.py", tmp_path)
    telemetry = tmp_path / ".trigger-tree"
    telemetry.mkdir()
    for name in ("CLAUDE_CODE_SESSION_ID", "CLAUDE_SESSION_ID", "TT_SESSION_ID"):
        monkeypatch.delenv(name, raising=False)
    fresh = datetime.now(timezone.utc).isoformat()
    telemetry.joinpath("history.jsonl").write_text(
        json.dumps({"t": "session", "session": "c", "ts": fresh, "client": "claude"}) + "\n"
    )
    status, message = mod.liveness_health()
    assert status == "PASS" and "recorded clients: claude" in message

    stale = "2020-01-01T00:00:00+00:00"
    telemetry.joinpath("history.jsonl").write_text(
        json.dumps({"t": "session", "session": "c", "ts": stale, "client": "claude"}) + "\n"
    )
    status, message = mod.liveness_health()
    assert status == "WARN" and "recorded clients: claude" in message
