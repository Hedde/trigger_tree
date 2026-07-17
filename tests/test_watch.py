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
    assert app._heat(10, 10) == mod.HEAT[-1]
    assert app._node_color(100, 0.9) == (mod.WHITE, True)
    assert app._node_color(100, 0.5) == (229, True)
    assert app._node_color(100, 0.0) == (100, False)


def test_render_and_truncation():
    mod = load_script("tt-watch.py", FIXTURE)
    files = [f"docs/f{i:02d}.md" for i in range(30)]
    app = mod.App(files)
    app.feed({"t": "read", "path": "docs/f00.md", "session": "S"})
    frame = "\n".join(app.render(time.time(), width=100, height=14))
    assert "TRIGGER TREE" in frame
    assert "quiet files hidden" in frame
    import re
    plain = re.sub(r"\x1b\[[0-9;]*m", "", frame)
    assert "1 reads" in plain


def test_tail_handles_rotation(tmp_path):
    mod = load_script("tt-watch.py", FIXTURE)
    p = tmp_path / "h.jsonl"
    tail = mod.Tail(str(p))
    assert tail.poll() == []  # file does not exist yet
    p.write_text('{"t":"read","path":"docs/a.md"}\n')
    assert tail.poll()[0]["path"] == "docs/a.md"
    p.write_text('{"t":"scan","path":"docs"}\n')  # smaller file: rotation/truncation
    assert tail.poll()[0]["t"] == "scan"


def test_demo_event_generator():
    mod = load_script("tt-watch.py", FIXTURE)
    import random
    gen = mod.demo_event(["docs/a.md", "docs/b.md"], random.Random(42))
    kinds = {next(gen)["t"] for _ in range(50)}
    assert kinds <= {"read", "scan", "skill"} and "read" in kinds


def test_main_demo_and_replay(monkeypatch, capsys):
    mod = load_script("tt-watch.py", FIXTURE)
    monkeypatch.setattr(sys, "argv", ["tt-watch.py", "--demo", "--seconds", "0.3"])
    mod.main()
    assert "--frame--" in capsys.readouterr().out

    mod = load_script("tt-watch.py", FIXTURE)
    monkeypatch.setattr(sys, "argv", ["tt-watch.py", "--replay", "--seconds", "0.3"])
    mod.main()
    assert "TRIGGER TREE" in capsys.readouterr().out
