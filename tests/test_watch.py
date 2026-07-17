import json
import sys
import time

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

    before = len(app.ticker)
    app.feed({"t": "read", "path": "docs/a.md", "session": "S"}, live=False)
    assert len(app.ticker) == before  # historic feed: counts only, no ticker


def test_heat_and_node_color():
    mod = load_script("tt-watch.py", FIXTURE)
    app = mod.App([])
    assert app._heat(0, 10) == mod.DEAD
    assert app._heat(1, 1000) == mod.GREEN
    assert app._heat(8, 20) == mod.AMBER
    assert app._heat(10, 10) == mod.RED
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
    assert "untouched" in frame  # quiet files collapse into a folder counter
    import re
    plain = re.sub(r"\x1b\[[0-9;]*m", "", frame)
    assert "1 reads" in plain and "q quit" in plain and "last event just now" in plain


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


def test_feed_discovers_unknown_path_and_long_names():
    mod = load_script("tt-watch.py", FIXTURE)
    app = mod.App(["docs/a.md"])
    app.feed({"t": "read", "path": "docs/brand-new-file.md", "session": "S"})
    assert "docs/brand-new-file.md" in app.files
    long_name = "docs/" + "x" * 40 + ".md"
    app.feed({"t": "read", "path": long_name, "session": "S"})
    frame = "\n".join(app.render(time.time(), width=120, height=40))
    assert "…" in frame  # long basename truncated


def _browse_app(mod):
    app = mod.App(["docs/a.md", "docs/b.md", "docs/c.md"])
    app.feed({"t": "prompt", "prompt": "style the buttons", "session": "S", "ts": "2026-07-01T09:00:00Z"})
    app.feed({"t": "read", "path": "docs/a.md", "session": "S", "ts": "2026-07-01T09:00:05Z"})
    app.feed({"t": "scan", "path": "docs", "session": "S", "ts": "2026-07-01T09:00:06Z"})
    app.feed({"t": "prompt", "prompt": "fix the migration", "session": "S", "ts": "2026-07-01T09:05:00Z"})
    app.feed({"t": "read", "path": "docs/b.md", "session": "S", "ts": "2026-07-01T09:05:05Z"})
    app.feed({"t": "skill", "skill": "deploy", "session": "S", "ts": "2026-07-01T09:05:09Z"})
    return app


def test_prompt_events_are_visible_live():
    mod = load_script("tt-watch.py", FIXTURE)
    app = mod.App(["docs/a.md"])
    app.feed({"t": "prompt", "prompt": "why is the build red and what do our docs say about it", "session": "S"})
    assert app.total_prompts == 1
    assert app.ticker[0][1] == "▸"  # typed prompt lands in the ticker immediately
    import re
    frame = re.sub(r"\x1b\[[0-9;]*m", "", "\n".join(app.render(time.time(), width=110, height=30)))
    assert "1 prompts" in frame
    assert '"why is the build red and what do our docs say about' in frame
    assert "[prompt]" not in frame  # the pseudo-agent tag is not rendered


def test_prompt_buckets_and_browsing():
    mod = load_script("tt-watch.py", FIXTURE)
    app = _browse_app(mod)
    assert len(app.buckets) == 2
    assert [b["prompt"] for b in app.buckets] == ["style the buttons", "fix the migration"]

    app.select_prev()                    # from live → newest prompt
    assert app.selected == 1
    frame = "\n".join(app.render(time.time(), width=110, height=30))
    assert "fix the migration" in frame and "▸ prompt 2/2" in frame
    assert "b.md" in frame and "a.md" not in frame          # filtered to this bucket
    assert "skill:deploy" in frame and "09:05:09" in frame  # bucket ticker with timestamps
    assert "] next" in frame

    app.select_prev()
    assert app.selected == 0
    frame = "\n".join(app.render(time.time(), width=110, height=30))
    assert "style the buttons" in frame and "a.md" in frame and "b.md" not in frame
    app.select_prev()
    assert app.selected == 0             # clamped at the oldest prompt

    app.select_next()
    app.select_next()                    # step past newest → back to live
    assert app.selected is None
    frame = "\n".join(app.render(time.time(), width=110, height=30))
    assert "browse prompts" in frame     # live hint restored


def test_reads_before_any_prompt_get_a_session_start_bucket():
    mod = load_script("tt-watch.py", FIXTURE)
    app = mod.App(["docs/a.md"])
    app.feed({"t": "read", "path": "docs/a.md", "session": "S", "ts": "2026-07-01T08:59:00Z"})
    assert app.buckets[0]["prompt"] == "(session start)"
    app.select_prev()
    assert "(session start)" in "\n".join(app.render(time.time(), width=100, height=30))


def test_handle_key_dispatch():
    mod = load_script("tt-watch.py", FIXTURE)
    app = _browse_app(mod)
    assert mod.handle_key(app, "q") is True
    assert mod.handle_key(app, "[") is False and app.selected == 1
    assert mod.handle_key(app, "]") is False and app.selected is None
    mod.handle_key(app, "[")
    assert mod.handle_key(app, "a") is False and app.selected is None
    assert mod.handle_key(app, "x") is False  # unknown keys are ignored
    empty = mod.App([])
    mod.handle_key(empty, "[")               # no buckets: stays live
    assert empty.selected is None
    mod.handle_key(empty, "]")               # ] in live mode is a no-op
    assert empty.selected is None


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


def test_main_demo_and_replay(monkeypatch, capsys):
    # first event fires at t+0.5s, so run just past it to exercise the feed branches
    mod = load_script("tt-watch.py", FIXTURE)
    monkeypatch.setattr(sys, "argv", ["tt-watch.py", "--demo", "--seconds", "0.7"])
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
    monkeypatch.setattr(sys, "argv", ["tt-watch.py", "--seconds", "0.5"])
    mod.main()
    plain = re.sub(r"\x1b\[[0-9;]*m", "", capsys.readouterr().out)
    assert "1 reads" in plain  # the live tail fed the appended event


def test_main_exits_on_keyboard_interrupt(monkeypatch, capsys):
    mod = load_script("tt-watch.py", FIXTURE)
    monkeypatch.setattr(sys, "argv", ["tt-watch.py"])  # no --seconds: only KI can stop it
    monkeypatch.setattr(mod.time, "sleep", lambda _: (_ for _ in ()).throw(KeyboardInterrupt))
    mod.main()  # must swallow the interrupt and restore cleanly
    assert "trigger-tree" in capsys.readouterr().out
