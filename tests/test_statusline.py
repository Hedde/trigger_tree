import hashlib
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


def test_session_summary_survives_history_rotation_and_avoids_rescan(tmp_path, monkeypatch, capsys):
    telemetry = tmp_path / ".trigger-tree"
    sessions = telemetry / "sessions"
    sessions.mkdir(parents=True)
    name = hashlib.sha256(b"S").hexdigest()[:32] + ".json"
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    (sessions / name).write_text(
        json.dumps(
            {
                "files": ["docs/a.md", "docs/deep/b.md"],
                "scans": 7,
                "last": {"t": "scan", "path": "docs/new", "ts": now},
            }
        )
    )
    (telemetry / "history-rotated.jsonl").write_text("not consulted")
    mod = load_script("tt-statusline.py", tmp_path)
    out = run_statusline(mod, monkeypatch, capsys, '{"session_id":"S"}')
    assert "2 files · 7 scans · 2 folders · depth 2" in out
    assert "docs/new/" in out


def test_statusline_includes_only_cached_mature_grade(tmp_path, monkeypatch, capsys):
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    write_history(
        tmp_path,
        [json.dumps({"t": "read", "ts": now, "session": "S", "path": "docs/a.md"})],
    )
    badge = tmp_path / ".trigger-tree" / "badge.json"
    badge.write_text(json.dumps({"message": "measuring…"}))
    mod = load_script("tt-statusline.py", tmp_path)
    assert " B ·" not in run_statusline(mod, monkeypatch, capsys, '{"session_id":"S"}')
    badge.write_text(json.dumps({"message": "B (82)"}))
    assert "🌳 B · 1 files" in run_statusline(mod, monkeypatch, capsys, '{"session_id":"S"}')


def test_session_summary_with_invalid_last_timestamp_is_cold(tmp_path, monkeypatch, capsys):
    sessions = tmp_path / ".trigger-tree" / "sessions"
    sessions.mkdir(parents=True)
    name = hashlib.sha256(b"S").hexdigest()[:32] + ".json"
    (sessions / name).write_text(
        json.dumps(
            {
                "files": ["docs/a.md"],
                "scans": 0,
                "last": {"t": "read", "path": "docs/a.md", "ts": "invalid"},
            }
        )
    )
    mod = load_script("tt-statusline.py", tmp_path)
    out = run_statusline(mod, monkeypatch, capsys, '{"session_id":"S"}')
    assert "○" in out and "docs/a.md" in out


def test_fresh_read_green_dot(tmp_path, monkeypatch, capsys):
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    write_history(
        tmp_path,
        [
            json.dumps({"t": "read", "ts": now, "session": "S", "path": "docs/ui/a.md"}),
            json.dumps({"t": "read", "ts": now, "session": "S", "path": "docs/b.md"}),
            '{"session":"S","torn',  # passes the session prefilter, fails JSON parse
        ],
    )
    mod = load_script("tt-statusline.py", tmp_path)
    out = run_statusline(mod, monkeypatch, capsys, '{"session_id":"S"}')
    assert "2 files · 0 scans · 2 folders · depth 2" in out
    assert "●" in out and mod.FRESH in out and "docs/b.md" in out


def test_scan_only_session_is_live_and_marks_folder_path(tmp_path, monkeypatch, capsys):
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    write_history(
        tmp_path,
        [
            json.dumps({"t": "session", "ts": now, "session": "S"}),
            json.dumps({"t": "scan", "ts": now, "session": "S", "path": "docs/backlog"}),
        ],
    )
    mod = load_script("tt-statusline.py", tmp_path)
    out = run_statusline(mod, monkeypatch, capsys, '{"session_id":"S"}')

    assert "0 files · 1 scans · 0 folders · depth 0" in out
    assert "●" in out and mod.FRESH in out and "docs/backlog/" in out


def test_statusline_strips_terminal_controls_from_event_path(tmp_path, monkeypatch, capsys):
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    path = "docs/safe\x1b]52;c;c3RvbGVu\x07\x1b[2J\u202eevil.md"
    write_history(tmp_path, [json.dumps({"t": "read", "ts": now, "session": "S", "path": path})])
    mod = load_script("tt-statusline.py", tmp_path)
    out = run_statusline(mod, monkeypatch, capsys, '{"session_id":"S"}')
    assert "\x1b]52" not in out and "\x1b[2J" not in out and "\x07" not in out
    assert "\u202e" not in out and "docs/safeevil.md" in out
    assert mod.terminal_safe("café 👩‍💻") == "café 👩‍💻"


def test_newer_scan_controls_freshness_but_read_stats_stay_read_derived(
    tmp_path, monkeypatch, capsys
):
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    write_history(
        tmp_path,
        [
            json.dumps({"t": "scan", "ts": now, "session": "S", "path": "docs/backlog"}),
            json.dumps(
                {
                    "t": "read",
                    "ts": "2020-01-01T00:00:00Z",
                    "session": "S",
                    "path": "docs/ui/a.md",
                }
            ),
        ],
    )
    mod = load_script("tt-statusline.py", tmp_path)
    out = run_statusline(mod, monkeypatch, capsys, '{"session_id":"S"}')

    assert "1 files · 1 scans · 1 folders · depth 2" in out
    assert "●" in out and mod.FRESH in out and "docs/backlog/" in out


def test_old_read_dim_dot(tmp_path, monkeypatch, capsys):
    write_history(
        tmp_path,
        [
            json.dumps(
                {"t": "read", "ts": "2020-01-01T00:00:00Z", "session": "S", "path": "docs/a.md"}
            ),
        ],
    )
    mod = load_script("tt-statusline.py", tmp_path)
    out = run_statusline(mod, monkeypatch, capsys, '{"session_id":"S"}')
    assert "○" in out and mod.COLD in out


def test_recent_read_amber_dot(tmp_path, monkeypatch, capsys):
    five_min_ago = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 300))
    write_history(
        tmp_path,
        [
            json.dumps({"t": "read", "ts": five_min_ago, "session": "S", "path": "docs/a.md"}),
        ],
    )
    mod = load_script("tt-statusline.py", tmp_path)
    out = run_statusline(mod, monkeypatch, capsys, '{"session_id":"S"}')
    assert "◐" in out and mod.WARM in out


def test_unparseable_timestamp_falls_back_to_cold(tmp_path, monkeypatch, capsys):
    write_history(
        tmp_path,
        [
            json.dumps({"t": "read", "ts": "not-a-ts", "session": "S", "path": "docs/a.md"}),
        ],
    )
    mod = load_script("tt-statusline.py", tmp_path)
    out = run_statusline(mod, monkeypatch, capsys, '{"session_id":"S"}')
    assert "○" in out and "docs/a.md" in out
