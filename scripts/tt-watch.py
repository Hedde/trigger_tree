#!/usr/bin/env python3
"""trigger-tree live watcher — colored ASCII pulse animation over the docs tree.

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

if os.name == "nt":  # pragma: no cover — Windows console setup
    os.system("")  # enables ANSI escape processing in the Windows terminal
try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:  # pragma: no cover — exotic stdout replacement
    pass

# Layered config: project override → plugin default → hardcoded. A partial or
# broken config.sh must never crash the watcher.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def _conf_texts():
    texts = []
    for path in (os.path.join(ROOT, ".trigger-tree", "config.sh"),
                 os.path.join(SCRIPT_DIR, "tt-config.sh")):
        try:
            texts.append(open(path, encoding="utf-8").read())
        except OSError:
            continue
    return texts


def _conf_regex(name, fallback):
    for text in _conf_texts():
        m = re.search(name + r"='([^']+)'", text)
        if m:
            try:
                return re.compile(m.group(1))
            except re.error:
                continue
    return re.compile(fallback)


WATCH = _conf_regex("TT_WATCH_REGEX", r"^docs/.*\.md$")
BASES = ["docs", "agents", "skills", "agent-briefs", ".claude/rules", ".claude/skills", "."]

SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
SPARK = " ▁▂▃▄▅▆▇█"
GREEN, AMBER, RED = 114, 214, 196  # three heat tiers, matching the website demo
DEAD, DIM, WHITE, FOLDER = 240, 245, 231, 250
BUCKET_LIMIT = 20       # detailed per-prompt buckets kept for browsing (totals aggregate all)
EVENTS_PER_BUCKET = 500  # cap against runaway tasks flooding one bucket
ESCAPE_BYTE_TIMEOUT = 0.2  # tolerate delayed terminal bytes on loaded machines
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
                rel = os.path.relpath(os.path.join(dirpath, f), ROOT).replace(os.sep, "/")
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
        self.total_prompts = 0
        self.sessions = set()
        self.last_event = None  # wall-clock of the last live-fed event
        self.buckets = []         # one bucket per typed prompt: its aggregated events
        self._current = {}        # session -> active bucket
        self.selected = None      # bucket index while browsing, None = live view

    def feed(self, ev, live=True):
        t = ev.get("t")
        if live:
            self.last_event = time.time()
        s_id = ev.get("session", "?")
        self.sessions.add(s_id)
        if t == "prompt":
            bucket = {"session": s_id, "ts": ev.get("ts", ""),
                      "prompt": (ev.get("prompt") or "").strip() or "(prompt)", "events": []}
            self.buckets.append(bucket)
            self._current[s_id] = bucket
            self.total_prompts += 1
            if len(self.buckets) > BUCKET_LIMIT:
                evicted = len(self.buckets) - BUCKET_LIMIT
                del self.buckets[:evicted]
                if self.selected is not None:
                    self.selected = max(0, self.selected - evicted)
            if live:  # a typed prompt is instantly visible: the pipeline is alive
                txt = bucket["prompt"][:44] + ("…" if len(bucket["prompt"]) > 44 else "")
                self.ticker.appendleft((time.time(), "▸", f'"{txt}"', "prompt"))
        elif t in ("read", "scan", "skill"):
            bucket = self._current.get(s_id)
            if bucket is None:
                bucket = {"session": s_id, "ts": ev.get("ts", ""),
                          "prompt": "(session start)", "events": []}
                self.buckets.append(bucket)
                self._current[s_id] = bucket
            bucket["events"].append({"t": t, "ts": ev.get("ts", ""),
                                     "path": ev.get("path") or f"skill:{ev.get('skill', '?')}",
                                     "agent": ev.get("agent", "main")})
            if len(bucket["events"]) > EVENTS_PER_BUCKET:
                del bucket["events"][:len(bucket["events"]) - EVENTS_PER_BUCKET]
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

    def select_prev(self):
        if not self.buckets:
            return
        self.selected = len(self.buckets) - 1 if self.selected is None else max(0, self.selected - 1)

    def select_next(self):
        if not self.buckets:
            return
        # A bounded timeline: right always means newer. It never wraps or
        # silently changes to the unrelated live overview (`a` does that).
        if self.selected is None:
            self.selected = len(self.buckets) - 1
        else:
            self.selected = min(len(self.buckets) - 1, self.selected + 1)

    def select_live(self):
        self.selected = None

    def _glow(self, node, now):
        t0 = self.pulses.get(node)
        if t0 is None or now < t0:
            return 0.0
        p = 1.0 - (now - t0) / PULSE_SECS
        return max(0.0, p)

    def _heat(self, count, max_count):
        if count <= 0:
            return DEAD
        level = math.log1p(count) / math.log1p(max(max_count, 2))
        if level < 0.45:
            return GREEN
        if level < 0.8:
            return AMBER
        return RED

    def _node_color(self, base, glow):
        if glow > 0.66:
            return WHITE, True
        if glow > 0.33:
            return 229, True
        return base, False

    def render(self, now, width, height):
        spin = SPINNER[int(now * 10) % len(SPINNER)]
        header = [
            c256(GREEN, f" {spin} ", bold=True)
            + c256(WHITE, "trigger-tree", bold=True)
            + c256(DIM, f"  {os.path.basename(ROOT)} · live doc-discovery"),
            "",
        ]
        browsing = self.selected is not None and 0 <= self.selected < len(self.buckets)
        if browsing:
            b = self.buckets[self.selected]
            counts = Counter(e["path"] for e in b["events"] if e["t"] == "read")
            b_scans = sum(1 for e in b["events"] if e["t"] == "scan")
            prompt_txt = b["prompt"][:56] + ("…" if len(b["prompt"]) > 56 else "")
            header.insert(1, c256(AMBER, f" ▸ prompt {self.selected + 1}/{len(self.buckets)} ", bold=True)
                          + c256(WHITE, f'"{prompt_txt}"')
                          + c256(DIM, f" · {sum(counts.values())} reads · {b_scans} scans"))
            files_src = sorted(counts)
        else:
            counts = self.counts
            files_src = self.files
        max_count = max(counts.values(), default=0)

        # group files per folder ("" = repo root)
        folders = {}
        for f in sorted(files_src):
            folders.setdefault(os.path.dirname(f), []).append(f)

        ticker_lines = min(3, len(self.ticker))
        fixed = len(header) + 2 + ticker_lines + 1  # footer + hint line
        budget = max(4, height - fixed)
        total = sum((1 if d else 0) + len(fs) for d, fs in folders.items())
        hide_quiet = total > budget

        body = []
        for folder in sorted(folders, key=lambda d: (d != "", d)):
            files = folders[folder]
            if hide_quiet:
                shown = [f for f in files if counts[f] or self._glow(f, now) > 0]
            else:
                shown = files
            hidden = len(files) - len(shown)
            if folder:
                color, bold = self._node_color(FOLDER, self._glow(folder, now))
                suffix = c256(DEAD, f"  ·{hidden} untouched") if hidden else ""
                body.append(c256(color, f" {folder}/", bold) + suffix)
            for i, f in enumerate(shown):
                count = counts[f]
                glow = self._glow(f, now)
                color, bold = self._node_color(self._heat(count, max_count), glow)
                branch = "└─" if i == len(shown) - 1 else "├─"
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
                body.append(c256(244 if folder else DIM, prefix)
                            + c256(color, name, bold) + pad + stat)

        if len(body) > budget:
            hidden_extra = len(body) - budget
            body = body[:budget]
            body.append(c256(DEAD, f"   … {hidden_extra} files hidden"))

        lines = header + body
        lines.append("")
        lines.append(
            c256(DIM, " ")
            + c256(WHITE, f"{self.total_prompts}", bold=True) + c256(DIM, " prompts · ")
            + c256(WHITE, f"{self.total_reads}", bold=True) + c256(DIM, " reads · ")
            + c256(WHITE, f"{self.total_scans}", bold=True) + c256(DIM, " scans (hunting) · ")
            + c256(WHITE, f"{self.total_skills}", bold=True) + c256(DIM, " skill uses · ")
            + c256(WHITE, f"{len(self.sessions)}", bold=True) + c256(DIM, " sessions")
        )
        if browsing:
            icons = {"read": "●", "scan": "🔍", "skill": "⚡"}
            for e in self.buckets[self.selected]["events"][-3:]:
                who = "" if e["agent"] == "main" else f" [{e['agent']}]"
                stamp = (e["ts"] or "")[11:19]
                lines.append(c256(DIM, f"   {icons[e['t']]} {e['path']}{who} · {stamp}"))
        else:
            for ts, icon, path, agent in list(self.ticker)[:3]:
                age = now - ts
                agestr = "just now" if age < 3 else (f"{age:.0f}s ago" if age < 60 else f"{age/60:.0f}m ago")
                who = "" if agent in ("main", "prompt") else f" [{agent}]"
                fade = DIM if age < 8 else DEAD
                lines.append(c256(fade, f"   {icon} {path}{who} · {agestr}"))
        if browsing:
            lines.append(c256(DEAD, "   ← older prompt · → newer prompt · a live overview · q quit"))
        else:
            if self.last_event is None:
                beat = "listening for doc reads (injected context never shows here)"
            else:
                age = now - self.last_event
                beat = "last event just now" if age < 3 else (
                    f"last event {age:.0f}s ago" if age < 60 else f"last event {age/60:.0f}m ago")
            lines.append(c256(DEAD, f"   ←/→ open newest prompt · q quit · live · {beat}"))
        return [ln[: width * 4] for ln in lines[:height]]  # *4: ANSI codes don't count


def normalize_escape(seq):
    """Map a terminal arrow-key escape tail to its bracket equivalent."""
    # Terminals may send CSI (`[C`), application-cursor (`OC`) or modified
    # variants (`[1;5C`). The final byte carries the direction in all of them.
    if seq.startswith(("[", "O")) and seq.endswith("D"):
        return "["
    if seq.startswith(("[", "O")) and seq.endswith("C"):
        return "]"
    return None


def normalize_windows(code):
    """Map a Windows console extended key code to its bracket equivalent."""
    return {"K": "[", "M": "]"}.get(code)


def read_key(fd):
    """Read one keypress from a raw fd, arrow escapes normalized to [ / ].

    Must use os.read, never sys.stdin: the buffered reader slurps the whole
    escape sequence off the fd in one read(1), the follow-up select() then sees
    an empty fd, and the leftover "[" is replayed on the *next* keypress — so
    every arrow key acted as "prev" one press late.
    """
    ch = os.read(fd, 1).decode(errors="replace")
    if ch == "\x1b":
        # Reads from a tty are allowed to return a partial escape sequence. Keep
        # consuming briefly until its final byte instead of leaving `[` behind
        # to be mistaken for "previous" on the next keypress.
        tail = bytearray()
        while len(tail) < 16 and select.select([fd], [], [], ESCAPE_BYTE_TIMEOUT)[0]:
            part = os.read(fd, 1)
            if not part:  # EOF after a lone escape; do not spin on a readable pipe
                return ""
            tail.extend(part)
            if tail and (65 <= tail[-1] <= 90 or tail[-1] == 126):
                return normalize_escape(tail.decode(errors="replace")) or ""
        ch = normalize_escape(tail.decode(errors="replace")) or ""
    return ch


def handle_key(app, ch):
    """Key dispatch for the interactive loop. Returns True when the watcher should quit."""
    if ch in ("q", "Q"):
        return True
    if ch == "[":
        app.select_prev()
    elif ch == "]":
        app.select_next()
    elif ch in ("a", "A"):
        app.select_live()
    return False


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
    use_termios = stdin_tty and os.name != "nt"
    old_term = None
    if is_tty:
        sys.stdout.write("\x1b[?1049h\x1b[?25l")
    if use_termios:  # pragma: no cover — needs a real tty
        import termios, tty
        old_term = termios.tcgetattr(sys.stdin)
        tty.setcbreak(sys.stdin.fileno())

    start = time.time()
    try:
        while True:
            now = time.time()
            if args.seconds and now - start >= args.seconds:
                break
            if os.name == "nt" and stdin_tty:  # pragma: no cover — Windows console keys
                import msvcrt
                if msvcrt.kbhit():
                    wch = msvcrt.getwch()
                    if wch in ("\x00", "\xe0"):
                        wch = normalize_windows(msvcrt.getwch()) or ""
                    if wch and handle_key(app, wch):
                        break
            elif use_termios and select.select([sys.stdin], [], [], 0)[0]:  # pragma: no cover
                ch = read_key(sys.stdin.fileno())
                if ch and handle_key(app, ch):
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
        if use_termios and old_term is not None:  # pragma: no cover — needs a real tty
            import termios
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_term)
        if is_tty:
            sys.stdout.write("\x1b[?25h\x1b[?1049l")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
