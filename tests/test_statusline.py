import io
import json
import sys
import time

from conftest import load_script


def run_statusline(mod, monkeypatch, capsys, stdin_text):
    monkeypatch.setattr(sys, "stdin", io.StringIO(stdin_text))
    mod.main()
    return capsys.readouterr().out


def write_history(project, lines):
    d = project / ".trigger-tree"
    d.mkdir(exist_ok=True)
    (d / "history.jsonl").write_text("\n".join(lines) + "\n")


def test_no_data(tmp_path, monkeypatch, capsys):
    mod = load_script("tt-statusline.py", tmp_path)
    assert "no data" in run_statusline(mod, monkeypatch, capsys, '{"session_id":"S"}')
    assert "no data" in run_statusline(mod, monkeypatch, capsys, "not-json")


def test_no_reads_for_session(tmp_path, monkeypatch, capsys):
    write_history(tmp_path, ['{"t":"session","ts":"2026-07-01T09:00:00Z","session":"OTHER"}'])
    mod = load_script("tt-statusline.py", tmp_path)
    assert "0 docs consulted" in run_statusline(mod, monkeypatch, capsys, '{"session_id":"S"}')


def test_fresh_read_green_dot(tmp_path, monkeypatch, capsys):
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    write_history(tmp_path, [
        json.dumps({"t": "read", "ts": now, "session": "S", "path": "docs/ui/a.md"}),
        json.dumps({"t": "read", "ts": now, "session": "S", "path": "docs/b.md"}),
        "torn{line",
    ])
    mod = load_script("tt-statusline.py", tmp_path)
    out = run_statusline(mod, monkeypatch, capsys, '{"session_id":"S"}')
    assert "2 files · 2 folders · depth 2" in out
    assert "●" in out and mod.FRESH in out and "docs/b.md" in out


def test_old_read_dim_dot(tmp_path, monkeypatch, capsys):
    write_history(tmp_path, [
        json.dumps({"t": "read", "ts": "2020-01-01T00:00:00Z", "session": "S", "path": "docs/a.md"}),
    ])
    mod = load_script("tt-statusline.py", tmp_path)
    out = run_statusline(mod, monkeypatch, capsys, '{"session_id":"S"}')
    assert "○" in out and mod.COLD in out
