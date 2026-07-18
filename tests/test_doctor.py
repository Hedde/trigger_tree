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
            '{"t":"session","ts":"2026-07-17T10:00:00Z"}\n{{torn\n'
        )


def test_doctor_all_checks_pass(tmp_path, capsys):
    wire_project(tmp_path)
    mod = load_script("tt-doctor.py", tmp_path)
    assert mod.main() == 0
    out = capsys.readouterr().out
    assert out.count("✓") == 4
    assert "1 valid events, latest 2026-07-17T10:00:00Z" in out
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
    monkeypatch.setattr(mod.os.path, "isfile", lambda _path: True)
    monkeypatch.setattr("builtins.open", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError()))
    assert mod.history_health() == ("FAIL", "telemetry: history exists but cannot be read")
