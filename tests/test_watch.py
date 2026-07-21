import os
import re
import sys
import time

import pytest
from conftest import FIXTURE, load_script


def plain(lines):
    return re.sub(r"\x1b\[[0-9;]*m", "", "\n".join(lines))


def test_terminal_render_strips_controls_but_preserves_unicode():
    mod = load_script("tt-watch.py", FIXTURE)
    attack = "safe\x1b]52;c;c3RvbGVu\x07\x1b[2J\r\u202eevil"
    app = mod.App(["docs/a.md"])
    app.feed({"t": "prompt", "prompt": attack, "session": "S"})
    app.feed({"t": "read", "path": "docs/a.md", "session": "S", "agent": attack})
    app.select_prev()
    rendered = "\n".join(app.render(time.time(), width=100, height=30))
    assert "\x1b]52" not in rendered and "\x1b[2J" not in rendered
    assert "\x07" not in rendered and "\r" not in rendered and "\u202e" not in rendered
    assert "safe" in rendered
    assert mod.terminal_safe("café 👩‍💻") == "café 👩‍💻"


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
    assert app._heat(0.2) == mod.COLD
    assert app._heat(1) == mod.COOL
    assert app._heat(2) == mod.GREEN
    assert app._heat(5) == mod.AMBER
    assert app._heat(10) == mod.RED
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


def test_sort_legend_is_permanent_clear_and_adaptive():
    mod = load_script("tt-watch.py", FIXTURE)
    app = mod.App(["docs/a.md"])
    wide = plain(app.render(time.time(), width=100, height=20))
    assert "sort:focus · [f] focus · [h] hot · [c] cold · [n] A–Z" in wide
    app.set_sort("cold")
    narrow = plain(app.render(time.time(), width=50, height=20))
    assert "sort:cold · [f]ocus [h]ot [c]old [n]A–Z [s]ettings" in narrow
    assert "←/→ prompts · q quit" in narrow  # navigation is a separate row


def test_name_sort_toggles_both_directions():
    mod = load_script("tt-watch.py", FIXTURE)
    app = mod.App(["docs/a.md", "docs/z.md"])
    app.set_sort("name")
    ascending = plain(app.render(time.time(), width=100, height=30))
    assert ascending.index("a.md") < ascending.index("z.md")
    app.set_sort("name")
    descending = plain(app.render(time.time(), width=100, height=30))
    assert "[n] Z–A" in descending
    assert descending.index("z.md") < descending.index("a.md")


def test_injected_files_are_labeled_and_stat_columns_align():
    mod = load_script("tt-watch.py", FIXTURE)
    app = mod.App(["CLAUDE.md", "AGENTS.md", "docs/a.md"])
    app.feed({"t": "read", "path": "CLAUDE.md", "session": "S"}, live=False)
    app.feed({"t": "read", "path": "docs/a.md", "session": "S"}, live=False)
    frame = plain(app.render(time.time(), width=110, height=30))
    claude = next(line for line in frame.splitlines() if "CLAUDE.md" in line)
    nested = next(line for line in frame.splitlines() if "a.md" in line)
    assert "injected · 1×" in claude
    assert claude.index("injected") == nested.index("·····")


def test_dashboard_prompt_settings_are_interactive_and_atomic(tmp_path, monkeypatch):
    mod = load_script("tt-watch.py", tmp_path)
    app = mod.App([])
    assert mod.handle_key(app, "s") is False and app.settings_open
    assert "Prompt privacy" in plain(app.render(time.time(), 100, 20))
    mod.handle_key(app, "3")
    config = tmp_path / ".trigger-tree" / "config.sh"
    assert "TT_LOG_PROMPTS='off'" in config.read_text()
    mod.handle_key(app, "1")
    assert "TT_LOG_PROMPTS='truncate'" in config.read_text()
    assert "Saved: truncate" in plain(app.render(time.time(), 100, 20))
    mod.handle_key(app, "s")
    assert not app.settings_open


def test_dashboard_settings_refuse_symlink_config(tmp_path):
    mod = load_script("tt-watch.py", tmp_path)
    telemetry = tmp_path / ".trigger-tree"
    telemetry.mkdir()
    victim = tmp_path / "victim"
    victim.write_text("safe")
    try:
        (telemetry / "config.sh").symlink_to(victim)
    except OSError:
        pytest.skip("symlinks unavailable")
    assert mod.save_prompt_mode("off") is False
    assert victim.read_text() == "safe"


def test_dashboard_settings_safe_fallback_and_cleanup(tmp_path, monkeypatch):
    mod = load_script("tt-watch.py", tmp_path)
    assert mod.prompt_mode() == "hash"
    monkeypatch.setattr(mod, "_conf_texts", lambda: [])
    assert mod.prompt_mode() == "hash"
    assert mod.save_prompt_mode("invalid") is False
    telemetry = tmp_path / ".trigger-tree"
    telemetry.symlink_to(tmp_path / "elsewhere")
    assert mod.save_prompt_mode("off") is False
    telemetry.unlink()

    def fail_replace(*_args):
        raise OSError("disk full")

    monkeypatch.setattr(mod.os, "replace", fail_replace)
    assert mod.save_prompt_mode("off") is False
    assert not list(telemetry.glob(".config.*"))


def test_heat_legend_is_coherent_permanent_and_adaptive():
    mod = load_script("tt-watch.py", FIXTURE)
    app = mod.App(["docs/a.md"])
    wide = plain(app.render(time.time(), width=100, height=20))
    assert "heat: cold → cool → active → warm → hot · · untouched" in wide
    narrow = plain(app.render(time.time(), width=50, height=20))
    assert "heat: cold→cool→active→warm→hot · · untouched" in narrow


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


def test_tail_retries_an_in_progress_append_exactly_once(tmp_path):
    mod = load_script("tt-watch.py", FIXTURE)
    p = tmp_path / "h.jsonl"
    p.write_bytes(b'{"t":"read","path":"docs/a')
    tail = mod.Tail(str(p), from_start=True)
    assert tail.poll() == []
    with open(p, "ab") as fh:
        fh.write(b'.md"}\n')
    assert tail.poll() == [{"t": "read", "path": "docs/a.md"}]
    assert tail.poll() == []


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
    frame = "\n".join(app.render(time.time(), width=60, height=40))
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


def test_hashed_prompt_is_identifiable_without_leaking_text():
    mod = load_script("tt-watch.py", FIXTURE)
    app = mod.App(["docs/a.md"])
    app.feed(
        {
            "t": "prompt",
            "prompt_hash": "a1b2c3d4e5",
            "session": "S",
            "ts": "2026-07-20T10:00:00Z",
        },
        live=False,
    )
    assert app.buckets[0]["prompt"] == "#a1b2c3d4e5"
    assert app.buckets[0]["prompt_kind"] == "hash"
    app.select_prev()
    frame = "\n".join(app.render(time.time(), width=150, height=30))
    assert '"#a1b2c3d4e5"' in frame
    assert "text hidden; set TT_LOG_PROMPTS='truncate' for future previews" in frame


def test_prompt_preview_uses_available_header_width():
    mod = load_script("tt-watch.py", FIXTURE)
    prompt = "explain which documentation governs the complete account migration workflow"
    app = mod.App([])
    app.feed({"t": "prompt", "prompt": prompt, "session": "S"}, live=False)
    app.select_prev()
    narrow = "\n".join(app.render(time.time(), width=70, height=20))
    wide = "\n".join(app.render(time.time(), width=150, height=20))
    assert "explain which documentat…" in narrow
    assert prompt in wide


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
    assert "[f] focus" in frame and "sort:focus" in frame  # live controls restored


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
    for key, mode in (("h", "hot"), ("c", "cold"), ("n", "name"), ("f", "focus")):
        app.select_prev()
        assert mod.handle_key(app, key) is False
        assert app.selected is None and app.sort_mode == mode
    assert mod.handle_key(app, "x") is False  # unknown keys are ignored
    empty = mod.App([])
    mod.handle_key(empty, "[")  # no buckets: stays live
    assert empty.selected is None
    mod.handle_key(empty, "]")  # no buckets: stays live
    assert empty.selected is None


def test_horizontal_heat_bars_dynamic_columns_and_hot_cold_sorting():
    mod = load_script("tt-watch.py", FIXTURE)
    files = [
        "docs/hot/a.md",
        "docs/cold/a.md",
        "docs/scanned/a.md",
        "docs/untouched/a.md",
    ]
    app = mod.App(files)
    app.feed(
        {"t": "read", "path": "docs/hot/a.md", "session": "S", "ts": "2026-07-20T12:00:00Z"},
        live=False,
    )
    for _ in range(20):
        app.feed({"t": "scan", "path": "docs/scanned", "session": "S"}, live=False)
    app.feed(
        {"t": "read", "path": "docs/cold/a.md", "session": "S", "ts": "2025-07-20T12:00:00Z"},
        live=False,
    )
    now = mod.timestamp_epoch("2026-07-20T12:00:00Z")

    app.set_sort("hot")
    hot = plain(app.render(now, width=100, height=30))
    assert hot.index("docs/hot/") < hot.index("docs/cold/")
    assert "docs/untouched/" not in hot and "docs/scanned/" not in hot
    assert "███" in hot and "h 1.0 · 1×" in hot

    app.set_sort("cold")
    cold = plain(app.render(now, width=100, height=30))
    assert (
        max(cold.index("docs/scanned/"), cold.index("docs/untouched/"))
        < cold.index("docs/cold/")
        < cold.index("docs/hot/")
    )
    assert "·····" in cold

    app.set_sort("name")
    named = plain(app.render(now, width=100, height=30))
    assert named.index("docs/cold/") < named.index("docs/hot/") < named.index("docs/scanned/")

    narrow_line = next(line for line in hot.splitlines() if "a.md" in line)
    app.set_sort("hot")
    wide = plain(app.render(now, width=140, height=30))
    wide_line = next(line for line in wide.splitlines() if "a.md" in line)
    assert wide_line.index("█") > narrow_line.index("█")


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
    mod = load_script("tt-watch.py", FIXTURE)
    monkeypatch.setattr(sys, "argv", ["tt-watch.py", "--demo", "--seconds", "1.5"])
    mod.main()
    assert "--frame--" in capsys.readouterr().out

    mod = load_script("tt-watch.py", FIXTURE)
    # Drive replay with a deterministic clock. A wall-clock deadline made macOS
    # coverage flaky when the shared runner was suspended before the first t+0.5s event.
    clock = [0.0]

    def tick():
        clock[0] += 0.1
        return clock[0]

    monkeypatch.setattr(mod.time, "time", tick)
    monkeypatch.setattr(mod.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(sys, "argv", ["tt-watch.py", "--replay", "--seconds", "2"])
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


def test_main_live_mode_resyncs_inventory_on_deterministic_clock(monkeypatch, capsys):
    mod = load_script("tt-watch.py", FIXTURE)
    clock = [0.0]
    calls = []

    def tick():
        clock[0] += 0.1
        return clock[0]

    original_inventory = mod.inventory

    def tracked_inventory():
        calls.append(clock[0])
        return original_inventory()

    monkeypatch.setattr(mod.time, "time", tick)
    monkeypatch.setattr(mod.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(mod, "inventory", tracked_inventory)
    monkeypatch.setattr(
        sys, "argv", ["tt-watch.py", "--seconds", str(mod.INVENTORY_SYNC_SECS + 0.5)]
    )
    mod.main()
    assert len(calls) == 2  # initial inventory plus one bounded-cadence live resync
    assert "trigger-tree" in capsys.readouterr().out


def test_heat_state_is_bounded_by_files_not_read_events():
    mod = load_script("tt-watch.py", FIXTURE)
    app = mod.App(["docs/a.md"])
    base = mod.timestamp_epoch("2026-07-20T12:00:00Z")
    for offset in range(10_000):
        app.feed(
            {
                "t": "read",
                "path": "docs/a.md",
                "session": "S",
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(base + offset)),
            },
            live=False,
        )
    assert len(app.read_heat) == 1
    assert len(app.read_heat["docs/a.md"]) == 2
    assert app.heat_scores(base + 9_999)["docs/a.md"] > 9_000


def test_client_detection_and_rotating_dashboard_tips(monkeypatch):
    mod = load_script("tt-watch.py", FIXTURE)
    monkeypatch.delenv("CLAUDE_PLUGIN_ROOT", raising=False)
    monkeypatch.delenv("CODEX_HOME", raising=False)
    monkeypatch.delenv("PLUGIN_ROOT", raising=False)
    assert mod.detect_client() is None
    monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", "/plugin")
    assert mod.detect_client() == "claude"
    assert mod.detect_client("codex") == "codex"
    monkeypatch.delenv("CLAUDE_PLUGIN_ROOT")
    monkeypatch.setenv("CODEX_HOME", "/codex")
    assert mod.detect_client() == "codex"
    tips = mod.load_tips("claude")
    assert tips and "/memory" in tips[0]
    assert mod.load_tips(None) == []
    monkeypatch.setattr(mod.importlib.util, "spec_from_file_location", lambda *_args: None)
    assert mod.load_tips("codex") == []

    app = mod.App(["docs/a.md"], ["first dashboard tip", "second dashboard tip"])
    first = plain(app.render(0, width=100, height=30))
    second = plain(app.render(mod.TIP_ROTATE_SECS, width=100, height=30))
    assert "tip: first dashboard tip" in first
    assert "tip: second dashboard tip" in second
    assert "…" in plain(app.render(0, width=20, height=30))
    app.feed({"t": "prompt", "prompt": "history", "session": "S"}, live=False)
    app.select_prev()
    assert "tip:" not in plain(app.render(0, width=100, height=30))


def test_crowded_dashboard_never_clips_tip_or_navigation_footer():
    mod = load_script("tt-watch.py", FIXTURE)
    files = [f"docs/backlog/{number:04d}-item.md" for number in range(80)]
    app = mod.App(files, ["Review project memory for stale guidance."])
    for number, path in enumerate(files):
        app.feed(
            {
                "t": "read",
                "path": path,
                "session": "S",
                "ts": f"2026-07-20T12:{number % 60:02d}:00Z",
            },
            live=False,
        )
    rendered = plain(app.render(0, width=120, height=35))
    assert len(rendered.splitlines()) <= 35
    assert "files hidden" in rendered
    assert "tip: Review project memory for stale guidance." in rendered
    assert "←/→ prompts · q quit" in rendered


def test_main_exits_on_keyboard_interrupt(monkeypatch, capsys):
    mod = load_script("tt-watch.py", FIXTURE)
    monkeypatch.setattr(sys, "argv", ["tt-watch.py"])  # no --seconds: only KI can stop it
    monkeypatch.setattr(mod.time, "sleep", lambda _: (_ for _ in ()).throw(KeyboardInterrupt))
    mod.main()  # must swallow the interrupt and restore cleanly
    assert "trigger-tree" in capsys.readouterr().out
