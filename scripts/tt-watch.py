#!/usr/bin/env python3
"""Trigger Tree live watcher — colored ASCII pulse animation over the docs tree.

Run in a second terminal pane next to a Claude Code session:

    python3 scripts/tt-watch.py            # live: tails .trigger-tree/history.jsonl
    python3 scripts/tt-watch.py --demo     # synthetic events, writes nothing
    python3 scripts/tt-watch.py --replay   # replays the real history, accelerated

A read makes its file flash white and ripples a pulse up through its parent
folders, then fades back to the file's heat color (read frequency). Untouched
paths stay dim gray. Quit with q or Ctrl+C. 256-color ANSI, stdlib only.
"""
import argparse
import glob as globmod
import json
import math
import os
import random
import re
import select
import shutil
import sys
import time
from collections import Counter, deque

ROOT = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
HIST = os.path.join(ROOT, ".trigger-tree", "history.jsonl")

# Project override wins over the plugin default (same rule as tt-log.py/tt-stats.py).
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_proj_conf = os.path.join(ROOT, ".trigger-tree", "config.sh")
_conf = open(_proj_conf if os.path.isfile(_proj_conf) else os.path.join(SCRIPT_DIR, "tt-config.sh")).read()
WATCH = re.compile(re.search(r"TT_WATCH_REGEX='([^']+)'", _conf).group(1))
BASES = ["docs", "agents", "skills", "agent-briefs", ".claude/rules", ".claude/skills", "."]

SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
SPARK = " ▁▂▃▄▅▆▇█"
HEAT = [108, 114, 148, 178, 214, 208, 202, 196]  # green → yellow → orange → red
DEAD, DIM, WHITE, FOLDER = 240, 245, 231, 250
PULSE_SECS = 1.4        # how long a flash takes to fade
RIPPLE_DELAY = 0.09     # per tree level, leaf → root


def c256(n, text, bold=False):
    return f"\x1b[{'1;' if bold else ''}38;5;{n}m{text}\x1b[0m"


def inventory():
    seen = set()
    for base in BASES:
        top = os.path.join(ROOT, base)
        if not os.path.isdir(top):
            continue
        walker = os.walk(top) if base != "." else [(top, [], os.listdir(top))]
        for dirpath, _, files in walker:
            for f in files:
                rel = os.path.relpath(os.path.join(dirpath, f), ROOT)
                if WATCH.search(rel):
                    seen.add(rel)
    return sorted(seen)


def all_history_files():
    return sorted(globmod.glob(os.path.join(ROOT, ".trigger-tree", "history*.jsonl")))


class Tail:
    """Follow history.jsonl; survives the file not existing yet."""

    def __init__(self, path, from_start=False):
        self.path = path
        self.pos = 0
        if not from_start and os.path.isfile(path):
            self.pos = os.path.getsize(path)

    def poll(self):
        if not os.path.isfile(self.path):
            return []
        size = os.path.getsize(self.path)
        if size < self.pos:  # truncated/rotated
            self.pos = 0
        if size == self.pos:
            return []
        with open(self.path) as fh:
            fh.seek(self.pos)
            chunk = fh.read()
            self.pos = fh.tell()
        events = []
        for line in chunk.splitlines():
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return events


def load_all_events():
    events = []
    for path in all_history_files():
        events.extend(Tail(path, from_start=True).poll())
    return events


class App:
    def __init__(self, files):
        self.files = list(files)
        self.counts = Counter()
        self.scans = Counter()
        self.pulses = {}          # node path -> pulse start time (may lie in the future)
        self.ticker = deque(maxlen=4)
        self.total_reads = 0
        self.total_scans = 0
        self.total_skills = 0
        self.sessions = set()

    def feed(self, ev, live=True):
        t = ev.get("t")
        self.sessions.add(ev.get("session", "?"))
        if t == "read":
            path = ev["path"]
            self.counts[path] += 1
            self.total_reads += 1
            if path not in self.files:
                self.files.append(path)
            if live:
                self._pulse(path)
                self.ticker.appendleft((time.time(), "●", path, ev.get("agent", "main")))
        elif t == "scan":
            self.scans[ev["path"]] += 1
            self.total_scans += 1
            if live:
                self._pulse(ev["path"])
                self.ticker.appendleft((time.time(), "🔍", ev["path"], ev.get("agent", "main")))
        elif t == "skill":
            self.total_skills += 1
            if live:
                skill_file = f".claude/skills/{ev.get('skill', '')}/SKILL.md"
                if skill_file in self.files:
                    self._pulse(skill_file)
                self.ticker.appendleft((time.time(), "⚡", f"skill:{ev.get('skill', '?')}",
                                        ev.get("agent", "main")))

    def _pulse(self, path):
        now = time.time()
        parts = path.split("/")
        # leaf flashes now, each ancestor a beat later: the ripple runs up the tree
        for i in range(len(parts), 0, -1):
            node = "/".join(parts[:i])
            t0 = now + (len(parts) - i) * RIPPLE_DELAY
            self.pulses[node] = max(self.pulses.get(node, 0), t0)

    def _glow(self, node, now):
        t0 = self.pulses.get(node)
        if t0 is None or now < t0:
            return 0.0
        p = 1.0 - (now - t0) / PULSE_SECS
        return max(0.0, p)

    def _heat(self, count, max_count):
        if count <= 0:
            return DEAD
        idx = int((len(HEAT) - 1) * math.log1p(count) / math.log1p(max(max_count, 2)))
        return HEAT[min(idx, len(HEAT) - 1)]

    def _node_color(self, base, glow):
        if glow > 0.66:
            return WHITE, True
        if glow > 0.33:
            return 229, True
        return base, False

    def render(self, now, width, height):
        max_count = max(self.counts.values(), default=0)
        spin = SPINNER[int(now * 10) % len(SPINNER)]
        lines = [
            c256(114, f" {spin} ", bold=True)
            + c256(WHITE, "TRIGGER TREE", bold=True)
            + c256(DIM, f"  {os.path.basename(ROOT)} · live doc-discovery"),
            "",
        ]

        # group files per folder ("" = repo root)
        folders = {}
        for f in sorted(self.files):
            folders.setdefault(os.path.dirname(f), []).append(f)

        body = []
        for folder in sorted(folders, key=lambda d: (d != "", d)):
            files = folders[folder]
            if folder:
                fcount = sum(self.counts[f] for f in files)
                color, bold = self._node_color(
                    FOLDER if fcount else DEAD, self._glow(folder, now)
                )
                quiet = sum(1 for f in files if not self.counts[f])
                suffix = c256(DEAD, f"  ·{quiet} untouched") if quiet else ""
                body.append(
                    (folder, True, c256(color, f" {folder}/", bold) + suffix)
                )
            for i, f in enumerate(files):
                count = self.counts[f]
                glow = self._glow(f, now)
                color, bold = self._node_color(self._heat(count, max_count), glow)
                branch = "└─" if i == len(files) - 1 else "├─"
                name = os.path.basename(f) if folder else f
                if len(name) > 34:
                    name = name[:33] + "…"
                pad = " " * max(1, 38 - len(name) - (3 if folder else 0))
                if count:
                    level = math.log1p(count) / math.log1p(max(max_count, 2))
                    spark = SPARK[max(1, int(level * (len(SPARK) - 1)))]
                    stat = c256(color, f"{spark} {count:>3}", bold)
                else:
                    stat = c256(DEAD, f"· {0:>3}")
                prefix = f"   {branch} " if folder else " "
                body.append(
                    (f, False,
                     c256(244 if folder else DIM, prefix)
                     + c256(color, name, bold) + pad + stat)
                )

        # fit to screen: drop quiet files first, then truncate
        budget = height - len(lines) - 5
        if len(body) > budget:
            keep, dropped = [], 0
            for path, is_folder, text in body:
                if is_folder or self.counts.get(path) or self._glow(path, now) > 0:
                    keep.append((path, is_folder, text))
                else:
                    dropped += 1
            body = keep
            if len(body) > budget:
                body, extra = body[:budget], len(body) - budget
                dropped += extra
            if dropped:
                body.append(("", True, c256(DEAD, f"   … {dropped} quiet files hidden")))

        lines.extend(text for _, _, text in body)
        lines.append("")
        lines.append(
            c256(DIM, " ")
            + c256(WHITE, f"{self.total_reads}") + c256(DIM, " reads · ")
            + c256(WHITE, f"{self.total_scans}") + c256(DIM, " scans (hunting) · ")
            + c256(WHITE, f"{self.total_skills}") + c256(DIM, " skill uses · ")
            + c256(WHITE, f"{len(self.sessions)}") + c256(DIM, " sessions")
        )
        for ts, icon, path, agent in list(self.ticker)[:3]:
            age = now - ts
            agestr = f"{age:.0f}s" if age < 60 else f"{age/60:.0f}m"
            who = "" if agent == "main" else f" [{agent}]"
            fade = DIM if age < 8 else DEAD
            lines.append(c256(fade, f"   {icon} {path}{who} · {agestr} ago"))
        return [ln[: width * 4] for ln in lines[:height]]  # *4: ANSI codes don't count


def demo_event(files, rng):
    hot = rng.sample(files, min(6, len(files)))  # a "task" keeps favoring a few files
    def gen():
        while True:
            roll = rng.random()
            if roll < 0.12:
                yield {"t": "scan", "path": rng.choice(["docs", "docs/development", "agents"]),
                       "session": "demo", "agent": "main"}
            elif roll < 0.2:
                yield {"t": "skill", "skill": rng.choice(["doc-update", "insights", "tt"]),
                       "session": "demo", "agent": "main"}
            else:
                pool = hot if rng.random() < 0.7 else files
                agent = rng.choice(["main", "main", "main", "Explore", "Plan"])
                yield {"t": "read", "path": rng.choice(pool), "session": "demo", "agent": agent}
    return gen()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--demo", action="store_true", help="synthetic events (writes nothing)")
    ap.add_argument("--replay", action="store_true", help="replay the real history, accelerated")
    ap.add_argument("--seconds", type=float, default=0, help="exit automatically after N seconds")
    args = ap.parse_args()

    app = App(inventory())
    tail = Tail(HIST)
    replay_events, replay_i = [], 0
    if args.replay:
        replay_events = load_all_events()
    else:
        for ev in load_all_events():
            app.feed(ev, live=False)  # historic counts, no flashing
    rng = random.Random()
    demo = demo_event(app.files or ["CLAUDE.md"], rng) if args.demo else None
    next_evt = time.time() + 0.5

    is_tty = sys.stdout.isatty()
    stdin_tty = sys.stdin.isatty()
    old_term = None
    if is_tty:
        sys.stdout.write("\x1b[?1049h\x1b[?25l")
    if stdin_tty:
        import termios, tty
        old_term = termios.tcgetattr(sys.stdin)
        tty.setcbreak(sys.stdin.fileno())

    start = time.time()
    try:
        while True:
            now = time.time()
            if args.seconds and now - start >= args.seconds:
                break
            if stdin_tty and select.select([sys.stdin], [], [], 0)[0]:
                if sys.stdin.read(1) in ("q", "Q"):
                    break
            if args.demo and now >= next_evt:
                app.feed(next(demo))
                next_evt = now + rng.uniform(0.3, 1.4)
            elif args.replay and now >= next_evt and replay_i < len(replay_events):
                app.feed(replay_events[replay_i])
                replay_i += 1
                next_evt = now + 0.35
            elif not args.demo and not args.replay:
                for ev in tail.poll():
                    app.feed(ev)
            size = shutil.get_terminal_size(fallback=(100, 34))
            frame = app.render(now, size.columns, size.lines)
            if is_tty:
                sys.stdout.write("\x1b[H" + "\x1b[K\n".join(frame) + "\x1b[0J")
            else:
                sys.stdout.write("\n".join(frame) + "\n--frame--\n")
            sys.stdout.flush()
            time.sleep(1 / 12)
    except KeyboardInterrupt:
        pass
    finally:
        if stdin_tty and old_term is not None:
            import termios
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_term)
        if is_tty:
            sys.stdout.write("\x1b[?25h\x1b[?1049l")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
