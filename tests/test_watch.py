import os
import sys
import time

import pytest
from conftest import FIXTURE, load_script


def test_app_feed_pulse_and_glow(tmp_path):
    mod = load_script("tt-watch.py", FIXTURE)
    app = mod.App(["docs/a.md", "docs/sub/b.md", ".claude/skills/deploy/SKILL.md"])
    t0 = time.time()
    app.feed({"t": "read", "path": "docs/sub/b.md", "session": "S", "agent": "Explore"})
    assert app.counts["docs/sub/b.md"] == 1 and app.total_reads == 1
    assert app.ticker[0][1] == "●" and app.ticker[0][3] == "Explore"
    # ripple: leaf pulses first, ancestors later
    assert app.pulses["docs/sub/b.md"] <= app.pulses["docs/sub"] <= app.pulses["docs"]
    assert app._glow("docs/sub/b.md", t0 + 0.1) > 0.9
    assert app._glow("docs/sub/b.md", t0 + 10) == 0.0
    assert app._glow("unknown", t0) == 0.0

    app.feed({"t": "scan", "path": "docs", "session": "S"})
    app.feed({"t": "skill", "skill": "deploy", "session": "S"})
    assert app.total_scans == 1 and app.total_skills == 1
    assert app.pulses.get(".claude/skills/deploy/SKILL.md")  # skill pulses its SKILL.md
    assert app.ticker[0][1] == "⚡"
    assert "SKILL.md" in "\n".join(app.render(time.time(), width=100, height=30))

    before = len(app.ticker)
    app.feed({"t": "read", "path": "docs/a.md", "session": "S"}, live=False)
    assert len(app.ticker) == before  # historic feed: counts only, no ticker


def test_heat_and_node_color():
    mod = load_script("tt-watch.py", FIXTURE)
    app = mod.App([])
    now = mod.timestamp_epoch("2026-07-20T12:00:00Z")
    app.feed(
        {"t": "read", "path": "docs/a.md", "session": "S", "ts": "2026-07-20T12:00:00Z"},
        live=False,
    )
    app.feed(
        {"t": "read", "path": "docs/a.md", "session": "S", "ts": "2026-06-20T12:00:00Z"},
        live=False,
    )
    assert app.heat_scores(now)["docs/a.md"] == pytest.approx(1.5)
    assert app.heat_scores(now + 30 * 86400)["docs/a.md"] == pytest.approx(0.75)
    assert mod.timestamp_epoch("bad") is None and mod.timestamp_epoch(None) is None
    assert app._heat(0) == mod.DEAD
    assert app._heat(1) == mod.GREEN
    assert app._heat(2) == mod.AMBER
    assert app._heat(5) == mod.RED
    assert app._node_color(100, 0.9) == (mod.WHITE, True)
    assert app._node_color(100, 0.5) == (229, True)
    assert app._node_color(100, 0.0) == (100, False)


def test_render_and_truncation():
    mod = load_script("tt-watch.py", FIXTURE)
    files = [f"docs/f{i:02d}.md" for i in range(30)]
    app = mod.App(files)
    app.feed({"t": "read", "path": "docs/f00.md", "session": "S"})
    frame = "\n".join(app.render(time.time(), width=100, height=14))
    assert "trigger-tree" in frame
    assert "29 unread" in frame  # unread coverage stays visible when quiet files collapse
    import re

    plain = re.sub(r"\x1b\[[0-9;]*m", "", frame)
    assert "1 reads" in plain and "q quit" in plain and "last event just now" in plain


def test_live_folders_prioritize_recent_activity_then_return_to_alpha():
    mod = load_script("tt-watch.py", FIXTURE)
    app = mod.App(["docs/alpha/a.md", "docs/zulu/z.md"])
    app.feed({"t": "read", "path": "docs/alpha/a.md", "session": "S"}, live=False)
    now = time.time()
    app.feed({"t": "read", "path": "docs/zulu/z.md", "session": "S"})

    recent = "\n".join(app.render(now, width=100, height=30))
    assert recent.index("docs/zulu/") < recent.index("docs/alpha/")
    assert app._folder_sort_key("", now, False) < app._folder_sort_key("docs/zulu", now, False)

    settled = "\n".join(app.render(now + mod.RECENT_SECS + 1, width=100, height=30))
    assert settled.index("docs/alpha/") < settled.index("docs/zulu/")
    assert app._folder_sort_key("docs/zulu", now, True)[-1] == "docs/zulu"


def test_live_focus_hides_untouched_folders_and_caps_activity_at_ten():
    mod = load_script("tt-watch.py", FIXTURE)
    files = [f"docs/f{i:02d}/a.md" for i in range(13)] + ["docs/quiet/a.md"]
    app = mod.App(files)
    for i in range(13):
        for _ in range(i + 1):
            app.feed({"t": "read", "path": f"docs/f{i:02d}/a.md", "session": "S"}, live=False)
    frame = "\n".join(app.render(time.time(), width=120, height=80))
    assert "docs/quiet/" not in frame
    assert "3 more active · 1 quiet folders · 1 unread hidden" in frame
    assert "docs/f12/" in frame and "docs/f00/" not in frame  # hottest ten win


def test_partial_or_broken_config_never_crashes(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.md").write_text("x")
    conf = tmp_path / ".trigger-tree"
    conf.mkdir()
    # partial config (the historic instant-crash in other projects)
    (conf / "config.sh").write_text("TT_LOG_PROMPTS='hash'\n")
    mod = load_script("tt-watch.py", tmp_path)
    assert mod.WATCH.search("agents/x.md")  # plugin default fills the gap
    # broken regex: skip it, fall through to the plugin default
    (conf / "config.sh").write_text("TT_WATCH_REGEX='([broken'\n")
    mod = load_script("tt-watch.py", tmp_path)
    assert mod.WATCH.search("docs/a.md")
    # hardcoded last resort when nothing defines the key at all
    assert mod._conf_regex("TT_MISSING", r"^x$").pattern == "^x$"


def test_tail_handles_rotation(tmp_path):
    mod = load_script("tt-watch.py", FIXTURE)
    p = tmp_path / "h.jsonl"
    tail = mod.Tail(str(p))
    assert tail.poll() == []  # file does not exist yet
    p.write_text('{"t":"read","path":"docs/a.md"}\ntorn{line\n')
    assert [e["path"] for e in tail.poll()] == ["docs/a.md"]  # torn line skipped
    assert tail.poll() == []  # unchanged file: nothing new
    p.write_text('{"t":"scan","path":"docs"}\n')  # smaller file: rotation/truncation
    assert tail.poll()[0]["t"] == "scan"


def test_feed_discovers_new_file_but_not_deleted_historical_path(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.md").write_text("x")
    mod = load_script("tt-watch.py", tmp_path)
    app = mod.App(["docs/a.md"])
    (tmp_path / "docs" / "brand-new-file.md").write_text("x")
    app.feed({"t": "read", "path": "docs/brand-new-file.md", "session": "S"})
    assert "docs/brand-new-file.md" in app.files
    app.feed({"t": "read", "path": "docs/deleted.md", "session": "old"}, live=False)
    assert "docs/deleted.md" not in app.files
    assert app.counts["docs/deleted.md"] == 1  # history retained, tree stays current
    long_name = "docs/" + "x" * 40 + ".md"
    (tmp_path / long_name).write_text("x")
    app.feed({"t": "read", "path": long_name, "session": "S"})
    frame = "\n".join(app.render(time.time(), width=120, height=40))
    assert "…" in frame  # long basename truncated


def test_inventory_sync_prunes_deleted_files_without_erasing_history(tmp_path):
    (tmp_path / "docs" / "adr").mkdir(parents=True)
    old = tmp_path / "docs" / "adr" / "old.md"
    old.write_text("x")
    mod = load_script("tt-watch.py", tmp_path)
    app = mod.App(["docs/adr/old.md"])
    app.feed({"t": "read", "path": "docs/adr/old.md", "session": "S"}, live=False)
    app.feed({"t": "scan", "path": "docs/adr", "session": "S"}, live=False)
    old.unlink()
    (tmp_path / "docs" / "adr").rmdir()
    app.sync_inventory(mod.inventory())
    import re

    frame = re.sub(r"\x1b\[[0-9;]*m", "", "\n".join(app.render(time.time(), 100, 30)))
    assert "docs/adr" not in frame
    assert app.total_reads == 1 and app.total_scans == 1
    app.select_prev()  # historical prompt/session context remains inspectable
    historic = re.sub(r"\x1b\[[0-9;]*m", "", "\n".join(app.render(time.time(), 100, 30)))
    assert "docs/adr" in historic


def _browse_app(mod):
    app = mod.App(["docs/a.md", "docs/b.md", "docs/c.md"])
    app.feed(
        {"t": "prompt", "prompt": "style the buttons", "session": "S", "ts": "2026-07-01T09:00:00Z"}
    )
    app.feed({"t": "read", "path": "docs/a.md", "session": "S", "ts": "2026-07-01T09:00:05Z"})
    app.feed({"t": "scan", "path": "docs", "session": "S", "ts": "2026-07-01T09:00:06Z"})
    app.feed(
        {"t": "prompt", "prompt": "fix the migration", "session": "S", "ts": "2026-07-01T09:05:00Z"}
    )
    app.feed({"t": "read", "path": "docs/b.md", "session": "S", "ts": "2026-07-01T09:05:05Z"})
    app.feed({"t": "skill", "skill": "deploy", "session": "S", "ts": "2026-07-01T09:05:09Z"})
    return app


def test_prompt_events_are_visible_live():
    mod = load_script("tt-watch.py", FIXTURE)
    app = mod.App(["docs/a.md"])
    app.feed(
        {
            "t": "prompt",
            "prompt": "why is the build red and what do our docs say about it",
            "session": "S",
        }
    )
    assert app.total_prompts == 1
    assert app.ticker[0][1] == "▸"  # typed prompt lands in the ticker immediately
    import re

    frame = re.sub(r"\x1b\[[0-9;]*m", "", "\n".join(app.render(time.time(), width=110, height=30)))
    assert "1 prompts" in frame
    assert '"why is the build red and what do our docs sa…"' in frame  # 44-char ticker cut
    assert "[prompt]" not in frame  # the pseudo-agent tag is not rendered


def test_prompt_buckets_and_browsing():
    mod = load_script("tt-watch.py", FIXTURE)
    app = _browse_app(mod)
    assert len(app.buckets) == 2
    assert [b["prompt"] for b in app.buckets] == ["style the buttons", "fix the migration"]

    app.select_prev()  # from live → newest prompt
    assert app.selected == 1
    frame = "\n".join(app.render(time.time(), width=110, height=30))
    assert "fix the migration" in frame and "▸ prompt 2/2" in frame
    assert "b.md" in frame and "a.md" not in frame  # filtered to this bucket
    assert "skill:deploy" in frame and "09:05:09" in frame  # bucket ticker with timestamps
    assert "→ newer prompt" in frame

    app.select_prev()
    assert app.selected == 0
    frame = "\n".join(app.render(time.time(), width=110, height=30))
    assert "style the buttons" in frame and "a.md" in frame and "b.md" not in frame
    assert "🔍 1 search" in frame and "2 unread" in frame
    app.select_prev()
    assert app.selected == 0  # clamped at the oldest prompt

    app.select_next()
    app.select_next()  # newest is a stable boundary
    assert app.selected == 1
    app.select_live()
    assert app.selected is None
    frame = "\n".join(app.render(time.time(), width=110, height=30))
    assert "open newest prompt" in frame  # live hint restored


def test_scan_only_prompt_shows_folder_search_without_faking_a_read():
    mod = load_script("tt-watch.py", FIXTURE)
    app = mod.App(["docs/ui/a.md", "docs/ui/b.md"])
    app.feed({"t": "prompt", "prompt": "find empty states", "session": "S"}, live=False)
    app.feed({"t": "scan", "path": "docs/ui", "session": "S", "agent": "Explore"}, live=False)
    app.select_prev()
    import re

    frame = re.sub(r"\x1b\[[0-9;]*m", "", "\n".join(app.render(time.time(), 100, 30)))
    assert "docs/ui/  · 🔍 1 search · 2 unread" in frame
    assert "0 reads · 1 scans" in frame
    assert "a.md" not in frame and "b.md" not in frame


def test_folder_counters_keep_searches_separate_from_unread_files(tmp_path):
    (tmp_path / "docs" / "ui").mkdir(parents=True)
    (tmp_path / "docs" / "ui" / "a.md").write_text("x")
    (tmp_path / "docs" / "ui" / "b.md").write_text("x")
    mod = load_script("tt-watch.py", tmp_path)
    app = mod.App(["docs/ui/a.md", "docs/ui/b.md"])
    app.feed({"t": "scan", "path": "docs/ui/", "session": "S"}, live=False)
    app.feed({"t": "scan", "path": "docs/ui/a.md", "session": "S"}, live=False)
    app.feed({"t": "read", "path": "docs/ui/a.md", "session": "S"}, live=False)
    import re

    frame = re.sub(r"\x1b\[[0-9;]*m", "", "\n".join(app.render(time.time(), 100, 30)))
    assert "docs/ui/  · 🔍 2 searches · 1 unread" in frame


def test_reads_before_any_prompt_get_a_session_start_bucket():
    mod = load_script("tt-watch.py", FIXTURE)
    app = mod.App(["docs/a.md"])
    app.feed({"t": "read", "path": "docs/a.md", "session": "S", "ts": "2026-07-01T08:59:00Z"})
    assert app.buckets[0]["prompt"] == "(session start)"
    app.select_prev()
    assert "(session start)" in "\n".join(app.render(time.time(), width=100, height=30))


def test_bucket_retention_keeps_last_20_but_totals_aggregate_all():
    mod = load_script("tt-watch.py", FIXTURE)
    app = mod.App(["docs/a.md"])
    for i in range(23):
        app.feed({"t": "prompt", "prompt": f"task {i}", "session": "S"})
        app.feed({"t": "read", "path": "docs/a.md", "session": "S"})
    assert len(app.buckets) == mod.BUCKET_LIMIT == 20  # detail: last 20 only
    assert app.buckets[0]["prompt"] == "task 3"  # oldest evicted
    assert app.total_prompts == 23 and app.total_reads == 23  # totals aggregate everything
    app.select_prev()
    app.selected = 0  # browse the oldest kept bucket
    app.feed({"t": "prompt", "prompt": "task 23", "session": "S"})
    assert app.selected == 0 and len(app.buckets) == 20  # selection clamps on eviction

    b = app.buckets[-1]
    b["events"] = [{"t": "read", "ts": "", "path": "docs/a.md", "agent": "main"}] * 600
    app.feed({"t": "read", "path": "docs/a.md", "session": "S"})
    assert len(app.buckets[-1]["events"]) <= mod.EVENTS_PER_BUCKET  # runaway tasks trimmed


def test_arrow_key_normalizers():
    mod = load_script("tt-watch.py", FIXTURE)
    assert mod.normalize_escape("[D") == "[" and mod.normalize_escape("[C") == "]"
    assert mod.normalize_escape("[A") is None  # up/down: ignored
    assert mod.normalize_escape("OC") == "]" and mod.normalize_escape("OD") == "["
    assert mod.normalize_escape("[1;5C") == "]" and mod.normalize_escape("[1;5D") == "["
    assert mod.normalize_windows("K") == "[" and mod.normalize_windows("M") == "]"
    assert mod.normalize_windows("H") is None


def test_read_key_consumes_full_escape_sequence():
    # Regression: buffered sys.stdin.read(1) slurped the whole escape sequence,
    # leaving a stray "[" that made every arrow key act as "prev" one press late.
    if os.name == "nt":
        pytest.skip("read_key is POSIX-only (select on a pipe fd)")
    mod = load_script("tt-watch.py", FIXTURE)
    r, w = os.pipe()
    try:
        os.write(w, b"\x1b[C\x1b[D\x1b[Cq")  # right, left, right, quit — back to back
        assert [mod.read_key(r) for _ in range(4)] == ["]", "[", "]", "q"]
    finally:
        os.close(r)
        os.close(w)


def test_read_key_ignores_lone_escape_at_eof():
    if os.name == "nt":
        pytest.skip("read_key is POSIX-only (select on a pipe fd)")
    mod = load_script("tt-watch.py", FIXTURE)
    r, w = os.pipe()
    os.write(w, b"\x1b")
    os.close(w)
    try:
        assert mod.read_key(r) == ""
    finally:
        os.close(r)


def test_read_key_ignores_timed_out_partial_escape():
    if os.name == "nt":
        pytest.skip("read_key is POSIX-only (select on a pipe fd)")
    mod = load_script("tt-watch.py", FIXTURE)
    r, w = os.pipe()
    try:
        os.write(w, b"\x1b[")
        assert mod.read_key(r) == ""
    finally:
        os.close(r)
        os.close(w)


@pytest.mark.skipif(os.name != "nt", reason="covers mocked POSIX decoder on Windows coverage run")
def test_read_key_posix_decoder_branches_under_windows(monkeypatch):
    mod = load_script("tt-watch.py", FIXTURE)

    def decode(reads, readiness):
        chunks = iter(reads)
        ready = iter(readiness)
        monkeypatch.setattr(mod.os, "read", lambda _fd, _size: next(chunks))
        monkeypatch.setattr(
            mod.select, "select", lambda *_args: ([1], [], []) if next(ready) else ([], [], [])
        )
        return mod.read_key(1)

    assert decode([b"q"], []) == "q"
    assert decode([b"\x1b", b"[", b"C"], [True, True]) == "]"
    assert decode([b"\x1b", b""], [True]) == ""
    assert decode([b"\x1b", b"["], [True, False]) == ""


def test_read_key_handles_fragmented_arrows_and_navigation_is_reversible():
    if os.name == "nt":
        pytest.skip("read_key is POSIX-only (select on a pipe fd)")
    import threading

    mod = load_script("tt-watch.py", FIXTURE)
    app = _browse_app(mod)
    r, w = os.pipe()

    def fragmented_right():
        for part in (b"\x1b", b"[", b"C"):
            os.write(w, part)
            time.sleep(0.005)

    try:
        os.write(w, b"\x1b[D")
        assert mod.handle_key(app, mod.read_key(r)) is False
        assert app.selected == 1  # live -> newest (2/2)
        os.write(w, b"\x1b[D")
        assert mod.handle_key(app, mod.read_key(r)) is False
        assert app.selected == 0  # left -> older (1/2)
        writer = threading.Thread(target=fragmented_right)
        writer.start()
        assert mod.handle_key(app, mod.read_key(r)) is False
        writer.join()
        assert app.selected == 1  # right reverses to newest (2/2)
    finally:
        os.close(r)
        os.close(w)


def test_handle_key_dispatch():
    mod = load_script("tt-watch.py", FIXTURE)
    app = _browse_app(mod)
    assert mod.handle_key(app, "q") is True
    assert mod.handle_key(app, "[") is False and app.selected == 1
    assert mod.handle_key(app, "]") is False and app.selected == 1
    assert mod.handle_key(app, "a") is False and app.selected is None
    assert mod.handle_key(app, "x") is False  # unknown keys are ignored
    empty = mod.App([])
    mod.handle_key(empty, "[")  # no buckets: stays live
    assert empty.selected is None
    mod.handle_key(empty, "]")  # no buckets: stays live
    assert empty.selected is None


def test_prompt_timeline_is_bounded_directional_and_reversible():
    mod = load_script("tt-watch.py", FIXTURE)
    app = _browse_app(mod)
    app.select_next()
    assert app.selected == 1  # either arrow opens newest from live
    app.select_prev()
    assert app.selected == 0  # left: 2/2 -> 1/2 (older)
    app.select_next()
    assert app.selected == 1  # right reverses: 1/2 -> 2/2
    app.select_next()
    assert app.selected == 1  # newest boundary stays put
    for _ in range(5):
        app.select_prev()
    assert app.selected == 0  # oldest boundary stays put


def test_heartbeat_when_no_live_events():
    mod = load_script("tt-watch.py", FIXTURE)
    app = mod.App(["docs/a.md"])
    app.feed({"t": "read", "path": "docs/a.md", "session": "S"}, live=False)
    frame = "\n".join(app.render(time.time(), width=100, height=30))
    assert "listening for doc reads" in frame
    app.last_event = time.time() - 120
    frame = "\n".join(app.render(time.time(), width=100, height=30))
    assert "last event 2m ago" in frame


def test_render_hard_truncation_of_read_files():
    mod = load_script("tt-watch.py", FIXTURE)
    files = [f"docs/f{i:02d}.md" for i in range(25)]
    app = mod.App(files)
    for f in files:  # every file read: quiet-file dropping can't help
        app.feed({"t": "read", "path": f, "session": "S"}, live=False)
    frame = "\n".join(app.render(time.time(), width=100, height=12))
    assert "files hidden" in frame
    app.select_prev()
    historic = "\n".join(app.render(time.time(), width=100, height=12))
    assert "files hidden" in historic  # compact prompt-history uses the same budget


def test_demo_event_generator():
    mod = load_script("tt-watch.py", FIXTURE)
    import random

    gen = mod.demo_event(["docs/a.md", "docs/b.md"], random.Random(42))
    kinds = {next(gen)["t"] for _ in range(50)}
    assert kinds <= {"read", "scan", "skill"} and "read" in kinds


def test_main_tty_mode_writes_alt_screen(monkeypatch, capsys):
    mod = load_script("tt-watch.py", FIXTURE)
    monkeypatch.setattr(sys, "argv", ["tt-watch.py", "--demo", "--seconds", "0.2"])
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True, raising=False)
    mod.main()
    out = capsys.readouterr().out
    assert "\x1b[?1049h" in out and "\x1b[?1049l" in out  # alt screen enter + restore
    assert "\x1b[?7l" in out and "\x1b[?7h" in out  # wrapping off + always restored
    assert "\x1b[3J" in out  # inherited scrollback is cleared once


def test_main_demo_and_replay(monkeypatch, capsys):
    # Leave ample scheduler margin beyond the first event at t+0.5s; coverage on
    # shared macOS runners can suspend the process around the old 0.7s boundary.
    mod = load_script("tt-watch.py", FIXTURE)
    monkeypatch.setattr(sys, "argv", ["tt-watch.py", "--demo", "--seconds", "1.5"])
    mod.main()
    assert "--frame--" in capsys.readouterr().out

    mod = load_script("tt-watch.py", FIXTURE)
    monkeypatch.setattr(sys, "argv", ["tt-watch.py", "--replay", "--seconds", "0.7"])
    mod.main()
    assert "trigger-tree" in capsys.readouterr().out


def test_main_live_mode_picks_up_appended_events(tmp_path, monkeypatch, capsys):
    import re
    import threading

    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.md").write_text("x")
    (tmp_path / ".trigger-tree").mkdir()
    hist = tmp_path / ".trigger-tree" / "history.jsonl"
    hist.write_text("")
    mod = load_script("tt-watch.py", tmp_path)

    def append_event():
        with open(hist, "a") as fh:
            fh.write('{"t":"read","path":"docs/a.md","session":"S","agent":"main"}\n')

    threading.Timer(0.05, append_event).start()
    monkeypatch.setattr(sys, "argv", ["tt-watch.py", "--seconds", "1.2"])
    mod.main()
    plain = re.sub(r"\x1b\[[0-9;]*m", "", capsys.readouterr().out)
    assert "1 reads" in plain  # the live tail fed the appended event


def test_main_exits_on_keyboard_interrupt(monkeypatch, capsys):
    mod = load_script("tt-watch.py", FIXTURE)
    monkeypatch.setattr(sys, "argv", ["tt-watch.py"])  # no --seconds: only KI can stop it
    monkeypatch.setattr(mod.time, "sleep", lambda _: (_ for _ in ()).throw(KeyboardInterrupt))
    mod.main()  # must swallow the interrupt and restore cleanly
    assert "trigger-tree" in capsys.readouterr().out
