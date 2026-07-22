#!/usr/bin/env python3
"""trigger-tree live watcher — colored ASCII pulse animation over the docs tree.

Run in a second terminal pane next to a Claude Code session:

    python3 scripts/tt-watch.py            # live: tails .trigger-tree/history.jsonl
    python3 scripts/tt-watch.py --demo     # synthetic events, writes nothing
    python3 scripts/tt-watch.py --replay   # replays the real history, accelerated

A read makes its file flash white and ripples a pulse up through its parent
folders, then fades back to the file's time-decayed heat color. Lifetime read
counts remain visible as separate evidence. Untouched
paths stay dim gray. Cold-to-hot activity uses a coherent blue → cyan → green →
amber → red spectrum. Quit with q or Ctrl+C. 256-color ANSI, stdlib only.
"""

import argparse
import glob as globmod
import importlib.util
import json
import math
import os
import random
import re
import select
import shutil
import sys
import tempfile
import time
import unicodedata
from collections import Counter, deque
from datetime import datetime, timezone

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
    for path in (
        os.path.join(ROOT, ".trigger-tree", "config.sh"),
        os.path.join(SCRIPT_DIR, "tt-config.sh"),
    ):
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
ALWAYS_LOADED = _conf_regex(
    "TT_ALWAYS_LOADED_REGEX",
    r"(^|/)(CLAUDE(?:\.local)?|AGENTS)\.md$|^\.claude/(rules|skills)/",
)
BASES = ["docs", "agents", "skills", "agent-briefs", ".claude/rules", ".claude/skills", "."]

SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
COLD, COOL, GREEN, AMBER, RED = 75, 80, 114, 214, 196
DEAD, DIM, WHITE = 240, 245, 231
BUCKET_LIMIT = 20  # detailed per-prompt buckets kept for browsing (totals aggregate all)
EVENTS_PER_BUCKET = 500  # cap against runaway tasks flooding one bucket
LIVE_FOLDER_LIMIT = 10  # focused live overview; full cold inventory lives in insights
ESCAPE_BYTE_TIMEOUT = 0.2  # tolerate delayed terminal bytes on loaded machines
PULSE_SECS = 1.4  # how long a flash takes to fade
RIPPLE_DELAY = 0.09  # per tree level, leaf → root
RECENT_SECS = 8.0  # keep recently active folders visible before alpha fallback
INVENTORY_SYNC_SECS = 5.0  # disk discovery is useful, but a full walk need not run per second
HEAT_HALF_LIFE_DAYS = 30.0
HEAT_DEAD_THRESHOLD = 0.05
INJECTED = 141
TIP_ROTATE_SECS = 30.0


def prompt_mode():
    for text in _conf_texts():
        match = re.search(r"TT_LOG_PROMPTS='(hash|truncate|off)'", text)
        if match:
            return match.group(1)
    return "hash"


def save_prompt_mode(mode):
    """Atomically update only prompt privacy in the project config."""
    if mode not in ("truncate", "hash", "off"):
        return False
    directory = os.path.join(ROOT, ".trigger-tree")
    config = os.path.join(directory, "config.sh")
    try:
        if os.path.lexists(directory) and os.path.islink(directory):
            return False
        os.makedirs(directory, mode=0o700, exist_ok=True)
        if os.path.lexists(config) and (os.path.islink(config) or not os.path.isfile(config)):
            return False
        try:
            text = open(config, encoding="utf-8").read()
        except FileNotFoundError:
            text = ""
        line = f"TT_LOG_PROMPTS='{mode}'"
        if re.search(r"^TT_LOG_PROMPTS='[^']*'", text, flags=re.M):
            text = re.sub(r"^TT_LOG_PROMPTS='[^']*'", line, text, flags=re.M)
        else:
            text = text.rstrip("\n") + ("\n" if text else "") + line + "\n"
        fd, temporary = tempfile.mkstemp(prefix=".config.", dir=directory, text=True)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(text)
            os.chmod(temporary, 0o600)
            os.replace(temporary, config)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return True
    except OSError:
        return False


def terminal_safe(value):
    """Strip terminal controls and invisible direction overrides from untrusted text."""
    bidi_controls = "\u061c\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069"
    text = re.sub(r"(?:\x1b\]|\x9d).*?(?:\x07|\x1b\\|\x9c)", "", str(value), flags=re.S)
    text = re.sub(r"(?:\x1b\[|\x9b)[0-?]*[ -/]*[@-~]", "", text)
    text = re.sub(r"\x1b[@-_]", "", text)
    return "".join(
        ch
        for ch in text
        if unicodedata.category(ch) not in ("Cc", "Cs") and ch not in bidi_controls
    )


def detect_client(explicit="auto"):
    if explicit in ("claude", "codex"):
        return explicit
    if os.environ.get("CODEX_HOME") or os.environ.get("PLUGIN_ROOT"):
        return "codex"
    if os.environ.get("CLAUDE_PLUGIN_ROOT"):
        return "claude"
    return None


def load_tips(client):
    if client not in ("claude", "codex"):
        return []
    path = os.path.join(SCRIPT_DIR, "tt-tips.py")
    try:
        spec = importlib.util.spec_from_file_location("trigger_tree_tips", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.tips_for(client, ROOT)
    except (AttributeError, OSError, ImportError):
        return []


def c256(n, text, bold=False):
    return f"\x1b[{'1;' if bold else ''}38;5;{n}m{terminal_safe(text)}\x1b[0m"


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


def timestamp_epoch(ts):
    try:
        return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()
    except (TypeError, ValueError):
        return None


class Tail:
    """Follow history.jsonl; survives the file not existing yet."""

    def __init__(self, path, from_start=False):
        self.path = path
        self.pos = 0
        self.pending = b""
        if not from_start and os.path.isfile(path):
            self.pos = os.path.getsize(path)

    def poll(self):
        if not os.path.isfile(self.path):
            return []
        size = os.path.getsize(self.path)
        if size < self.pos:  # truncated/rotated
            self.pos = 0
            self.pending = b""
        if size == self.pos:
            return []
        with open(self.path, "rb") as fh:
            fh.seek(self.pos)
            chunk = fh.read()
            self.pos = fh.tell()
        chunk = self.pending + chunk
        lines = chunk.split(b"\n")
        self.pending = lines.pop()  # an unterminated append is retried on the next poll
        events = []
        for line in lines:
            try:
                events.append(json.loads(line.decode("utf-8")))
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
        return events


def iter_all_events():
    """Stream archived history in order without retaining a second full copy."""
    for path in all_history_files():
        yield from Tail(path, from_start=True).poll()


def load_all_events():
    """Materialize history only for accelerated replay, which needs indexing."""
    return list(iter_all_events())


class App:
    def __init__(self, files, tips=None):
        self.files = list(files)
        self.counts = Counter()
        # path -> (decayed score at reference timestamp, reference timestamp).
        # This preserves exponential heat without retaining every historical read.
        self.read_heat = {}
        self.scans = Counter()
        self.pulses = {}  # node path -> pulse start time (may lie in the future)
        self.ticker = deque(maxlen=4)
        self.total_reads = 0
        self.total_scans = 0
        self.total_skills = 0
        self.total_prompts = 0
        self.sessions = set()
        self.last_event = None  # wall-clock of the last live-fed event
        self.buckets = []  # one bucket per typed prompt: its aggregated events
        self._current = {}  # session -> active bucket
        self.selected = None  # bucket index while browsing, None = live view
        self.sort_mode = "focus"  # focus | hot | cold | name
        self.name_desc = False
        self.settings_open = False
        self.settings_message = ""
        self.tips = list(tips or [])

    def sync_inventory(self, files):
        """Make the live tree reflect disk; historical counters remain intact."""
        self.files = sorted(set(files))

    def _trim_buckets(self):
        """Bound both browseable buckets and per-session references to them."""
        if len(self.buckets) <= BUCKET_LIMIT:
            return
        evicted_count = len(self.buckets) - BUCKET_LIMIT
        evicted = self.buckets[:evicted_count]
        del self.buckets[:evicted_count]
        for bucket in evicted:
            session = bucket["session"]
            if self._current.get(session) is bucket:
                del self._current[session]
        if self.selected is not None:
            self.selected = max(0, self.selected - evicted_count)

    def feed(self, ev, live=True):
        t = ev.get("t")
        if live:
            self.last_event = time.time()
        s_id = ev.get("session", "?")
        self.sessions.add(s_id)
        if t == "prompt":
            prompt_text = (ev.get("prompt") or "").strip()
            prompt_hash = (ev.get("prompt_hash") or "").strip()
            bucket = {
                "session": s_id,
                "ts": ev.get("ts", ""),
                "prompt": prompt_text
                or (f"#{prompt_hash}" if prompt_hash else "(prompt text off)"),
                "prompt_kind": "text" if prompt_text else "hash" if prompt_hash else "off",
                "events": [],
            }
            self.buckets.append(bucket)
            self._current[s_id] = bucket
            self.total_prompts += 1
            self._trim_buckets()
            if live:  # a typed prompt is instantly visible: the pipeline is alive
                txt = bucket["prompt"][:44] + ("…" if len(bucket["prompt"]) > 44 else "")
                self.ticker.appendleft((time.time(), "▸", f'"{txt}"', "prompt"))
        elif t in ("read", "scan", "skill"):
            bucket = self._current.get(s_id)
            if bucket is None:
                bucket = {
                    "session": s_id,
                    "ts": ev.get("ts", ""),
                    "prompt": "(session start)",
                    "prompt_kind": "synthetic",
                    "events": [],
                }
                self.buckets.append(bucket)
                self._current[s_id] = bucket
                self._trim_buckets()
            bucket["events"].append(
                {
                    "t": t,
                    "ts": ev.get("ts", ""),
                    "path": ev.get("path") or f"skill:{ev.get('skill', '?')}",
                    "agent": ev.get("agent", "main"),
                }
            )
            if len(bucket["events"]) > EVENTS_PER_BUCKET:
                del bucket["events"][: len(bucket["events"]) - EVENTS_PER_BUCKET]
        if t == "read":
            path = ev["path"]
            self.counts[path] += 1
            timestamp = timestamp_epoch(ev.get("ts"))
            if timestamp is None and live:
                timestamp = time.time()
            if timestamp is not None:
                self._record_heat(path, timestamp)
            self.total_reads += 1
            if path not in self.files and os.path.isfile(os.path.join(ROOT, path)):
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
                self.ticker.appendleft(
                    (time.time(), "⚡", f"skill:{ev.get('skill', '?')}", ev.get("agent", "main"))
                )

    def _pulse(self, path):
        now = time.time()
        parts = path.split("/")
        # leaf flashes now, each ancestor a beat later: the ripple runs up the tree
        for i in range(len(parts), 0, -1):
            node = "/".join(parts[:i])
            t0 = now + (len(parts) - i) * RIPPLE_DELAY
            self.pulses[node] = max(self.pulses.get(node, 0), t0)

    def _record_heat(self, path, timestamp):
        half_life_seconds = HEAT_HALF_LIFE_DAYS * 86400
        previous = self.read_heat.get(path)
        if previous is None:
            self.read_heat[path] = (1.0, timestamp)
            return
        score, reference = previous
        if timestamp >= reference:
            score *= 0.5 ** ((timestamp - reference) / half_life_seconds)
            self.read_heat[path] = (score + 1.0, timestamp)
        else:
            # History should normally be chronological, but rotated/imported logs
            # can be out of order. Add an older contribution at the current reference.
            score += 0.5 ** ((reference - timestamp) / half_life_seconds)
            self.read_heat[path] = (score, reference)

    def select_prev(self):
        if not self.buckets:
            return
        self.selected = (
            len(self.buckets) - 1 if self.selected is None else max(0, self.selected - 1)
        )

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

    def set_sort(self, mode):
        if mode in ("focus", "hot", "cold", "name"):
            if mode == "name" and self.sort_mode == "name":
                self.name_desc = not self.name_desc
            elif mode == "name":
                self.name_desc = False
            self.sort_mode = mode
            self.selected = None

    def set_prompt_mode(self, mode):
        self.settings_message = (
            f"Saved: {mode} (new prompts only)"
            if save_prompt_mode(mode)
            else "Could not safely update .trigger-tree/config.sh"
        )

    def _glow(self, node, now):
        t0 = self.pulses.get(node)
        if t0 is None or now < t0:
            return 0.0
        p = 1.0 - (now - t0) / PULSE_SECS
        return max(0.0, p)

    def heat_scores(self, now):
        """Current attention per file; lifetime counts deliberately stay separate."""
        half_life_seconds = HEAT_HALF_LIFE_DAYS * 86400
        return Counter(
            {
                path: score * 0.5 ** (max(0.0, now - reference) / half_life_seconds)
                for path, (score, reference) in self.read_heat.items()
            }
        )

    def _heat(self, score):
        if score < HEAT_DEAD_THRESHOLD:
            return DEAD
        if score < 0.5:
            return COLD
        if score < 2:
            return COOL
        if score < 5:
            return GREEN
        if score < 10:
            return AMBER
        return RED

    def _node_color(self, base, glow):
        if glow > 0.66:
            return WHITE, True
        if glow > 0.33:
            return 229, True
        return base, False

    def _folder_sort_key(self, folder, now, browsing, activity=0):
        """Prioritize live activity without making the tree permanently jumpy."""
        if not folder or browsing:
            return (folder != "", 1, 0, -activity, folder)
        if self.sort_mode == "hot":
            return (True, 0, 0, -activity, folder)
        if self.sort_mode == "cold":
            return (True, 0, 0, activity, folder)
        if self.sort_mode == "name":
            return (True, 0, 0, 0, folder)
        touched = self.pulses.get(folder, 0)
        recent = self._is_recent(folder, now)
        return (True, 0 if recent else 1, -touched if recent else 0, -activity, folder)

    def _is_recent(self, node, now):
        """A scheduled ripple is active immediately, not only after it starts glowing."""
        touched = self.pulses.get(node, 0)
        return bool(touched and now - touched <= RECENT_SECS)

    def _heat_bar(self, score, max_score, cells=5):
        if score < HEAT_DEAD_THRESHOLD:
            return "·" * cells
        filled = max(1, round(cells * math.log1p(score) / math.log1p(max(max_score, 2))))
        return "█" * min(cells, filled) + "·" * max(0, cells - filled)

    def _sort_legend(self, width):
        name_label = "Z–A" if self.name_desc else "A–Z"
        if width < 75:
            return f" sort:{self.sort_mode} · [f]ocus [h]ot [c]old [n]{name_label} [s]ettings"
        return (
            f" sort:{self.sort_mode} · [f] focus · [h] hot · [c] cold · "
            f"[n] {name_label} · [s] settings"
        )

    def _heat_legend(self, width):
        labels = (
            (COLD, "cold"),
            (COOL, "cool"),
            (GREEN, "active"),
            (AMBER, "warm"),
            (RED, "hot"),
        )
        separator = "→" if width < 75 else " → "
        scale = separator.join(c256(color, label, bold=True) for color, label in labels)
        return c256(DIM, " heat: ") + scale + c256(DEAD, " · · untouched")

    def _tip_line(self, now, width):
        if not self.tips:
            return None
        tip = self.tips[int(now // TIP_ROTATE_SECS) % len(self.tips)]
        room = max(12, width - 9)
        if len(tip) > room:
            tip = tip[: room - 1] + "…"
        return c256(DIM, " tip: ") + c256(COOL, tip)

    def render(self, now, width, height):
        spin = SPINNER[int(now * 10) % len(SPINNER)]
        header = [
            c256(GREEN, f" {spin} ", bold=True)
            + c256(WHITE, "trigger-tree", bold=True)
            + c256(DIM, f"  {os.path.basename(ROOT)} · live doc-discovery"),
            "",
        ]
        if self.settings_open:
            current = prompt_mode()
            choices = (
                ("1", "truncate", "local previews (first 200 characters)"),
                ("2", "hash", "fingerprints only (repeat prompts remain linkable)"),
                ("3", "off", "markers only (maximum privacy)"),
            )
            lines = header + [c256(WHITE, " Prompt privacy", bold=True), ""]
            for key, mode, description in choices:
                marker = "●" if mode == current else "○"
                color = GREEN if mode == current else DIM
                lines.append(c256(color, f"  [{key}] {marker} {mode:<8}  {description}"))
            lines += [
                "",
                c256(AMBER, f"  {self.settings_message}") if self.settings_message else "",
            ]
            lines.append(c256(DEAD, "  s/Esc back · changes apply to future prompts only"))
            return lines[:height]
        browsing = self.selected is not None and 0 <= self.selected < len(self.buckets)
        if browsing:
            b = self.buckets[self.selected]
            counts = Counter(e["path"] for e in b["events"] if e["t"] == "read")
            scan_counts = Counter(e["path"].rstrip("/") for e in b["events"] if e["t"] == "scan")
            b_scans = sum(scan_counts.values())
            prompt_room = max(18, min(120, width - 46))
            prompt_txt = b["prompt"][:prompt_room] + ("…" if len(b["prompt"]) > prompt_room else "")
            privacy_hint = (
                " · text hidden; set TT_LOG_PROMPTS='truncate' for future previews"
                if b.get("prompt_kind") == "hash"
                else ""
            )
            header.insert(
                1,
                c256(AMBER, f" ▸ prompt {self.selected + 1}/{len(self.buckets)} ", bold=True)
                + c256(WHITE, f'"{prompt_txt}"')
                + c256(
                    DIM,
                    f" · {sum(counts.values())} reads · {b_scans} scans{privacy_hint}",
                ),
            )
            files_src = sorted(counts)
            heat_scores = Counter(counts)
        else:
            counts = Counter(
                {path: count for path, count in self.counts.items() if path in self.files}
            )
            scan_counts = Counter({path.rstrip("/"): count for path, count in self.scans.items()})
            files_src = self.files
            heat_scores = Counter(
                {path: score for path, score in self.heat_scores(now).items() if path in self.files}
            )
        max_heat = max(heat_scores.values(), default=0)

        # group files per folder ("" = repo root)
        folders = {}
        for f in sorted(files_src):
            folders.setdefault(os.path.dirname(f), []).append(f)
        inventory_folders = {}
        for f in self.files:
            inventory_folders.setdefault(os.path.dirname(f), []).append(f)
        # A scan-only prompt still needs a visible folder row. Search targets are
        # directories in normal telemetry; a markdown target is filed by parent.
        normalized_scans = Counter()
        for target, count in scan_counts.items():
            folder = os.path.dirname(target) if target.lower().endswith(".md") else target
            if not browsing and not os.path.isdir(os.path.join(ROOT, folder)):
                continue  # deleted historical folders do not reappear in live view
            normalized_scans[folder] += count
            folders.setdefault(folder, [])

        focus_summary = ""
        folder_activity = {}
        folder_heat = {}
        for folder, files in folders.items():
            # Injected instructions are context, not thermal evidence. They may
            # remain visible in focus/name views but must not influence hot/cold
            # folder ordering or make a cold inventory claim about themselves.
            current_heat = sum(heat_scores[f] for f in files if not ALWAYS_LOADED.search(f))
            folder_heat[folder] = current_heat
            # Timestamp-less legacy reads have no honest heat. Keep their folder
            # visible and deterministically ordered by lifetime count instead.
            folder_activity[folder] = (
                current_heat or sum(counts[f] for f in files)
            ) + normalized_scans[folder]
        folder_order = (
            folder_heat if self.sort_mode in ("hot", "cold") and not browsing else folder_activity
        )
        if not browsing:
            active = [
                folder
                for folder in folders
                if any(counts[f] for f in folders[folder])
                or normalized_scans[folder]
                or self._is_recent(folder, now)
            ]
            if self.sort_mode in ("cold", "name"):
                candidates = list(folders)
                if self.sort_mode == "cold":
                    candidates = [
                        folder
                        for folder in candidates
                        if any(not ALWAYS_LOADED.search(path) for path in folders[folder])
                    ]
            elif self.sort_mode == "hot":
                candidates = [
                    folder for folder in folders if any(counts[f] for f in folders[folder])
                ]
            else:
                candidates = active
            candidates.sort(
                key=lambda folder: self._folder_sort_key(folder, now, False, folder_order[folder])
            )
            if self.sort_mode == "name" and self.name_desc:
                candidates.sort(key=lambda folder: (folder == "", folder), reverse=True)
            shown_folders = set(candidates[:LIVE_FOLDER_LIMIT])
            more_active = max(0, len(candidates) - len(shown_folders))
            quiet = [folder for folder in folders if folder not in active]
            quiet_unread = sum(len(inventory_folders.get(folder, [])) for folder in quiet)
            folders = {
                folder: files for folder, files in folders.items() if folder in shown_folders
            }
            summary = []
            if more_active:
                label = "more folders" if self.sort_mode in ("cold", "name") else "more active"
                summary.append(f"{more_active} {label}")
            if quiet and self.sort_mode in ("focus", "hot"):
                summary.append(f"{len(quiet)} quiet folders · {quiet_unread} unread")
            if summary:
                focus_summary = "   … " + " · ".join(summary) + " hidden"

        ticker_lines = min(3, len(self.ticker))
        tip_line = None if browsing else self._tip_line(now, width)
        # Body overflow adds a visible "files hidden" row and focus mode may
        # add its own summary. Reserve both up front: the live footer (including
        # its tip and key legend) must never be pushed below the terminal edge.
        overflow_rows = 1
        summary_rows = 1 if focus_summary else 0
        fixed = len(header) + 2 + ticker_lines + 3 + bool(tip_line) + overflow_rows + summary_rows
        budget = max(4, height - fixed)
        total = sum((1 if d else 0) + len(fs) for d, fs in folders.items())
        hide_quiet = total > budget

        body = []
        stat_width = 8 if browsing else 16
        name_column = max(18, width - stat_width - 8)
        rendered_folders = sorted(
            folders,
            key=lambda d: self._folder_sort_key(d, now, browsing, folder_order.get(d, 0)),
        )
        if not browsing and self.sort_mode == "name" and self.name_desc:
            rendered_folders = sorted(rendered_folders, reverse=True)
        for folder in rendered_folders:
            files = folders[folder]
            if not browsing and self.sort_mode == "hot":
                files = sorted(files, key=lambda f: (-heat_scores[f], f))
            elif not browsing and self.sort_mode == "cold":
                files = sorted(
                    files, key=lambda f: (bool(ALWAYS_LOADED.search(f)), heat_scores[f], f)
                )
            elif not browsing and self.sort_mode == "name":
                files = sorted(files, reverse=self.name_desc)
            if not browsing:
                if self.sort_mode == "cold":
                    shown = [f for f in files if not ALWAYS_LOADED.search(f)]
                elif self.sort_mode == "name":
                    shown = files
                else:
                    shown = [f for f in files if counts[f] or self._glow(f, now) > 0]
            elif hide_quiet:
                shown = [f for f in files if counts[f] or self._glow(f, now) > 0]
            else:
                shown = files
            if folder:
                color, bold = self._node_color(
                    self._heat(folder_heat.get(folder, 0)), self._glow(folder, now)
                )
                searches = normalized_scans[folder]
                unread = sum(1 for f in inventory_folders.get(folder, []) if not counts[f])
                status = []
                if searches:
                    status.append(f"🔍 {searches} search{'es' if searches != 1 else ''}")
                if unread:
                    status.append(f"{unread} unread")
                suffix = c256(DEAD, "  · " + " · ".join(status)) if status else ""
                body.append(c256(color, f" {folder}/", bold) + suffix)
            for i, f in enumerate(shown):
                count = counts[f]
                heat = heat_scores[f]
                injected = bool(ALWAYS_LOADED.search(f))
                glow = self._glow(f, now)
                color, bold = self._node_color(INJECTED if injected else self._heat(heat), glow)
                branch = "└─" if i == len(shown) - 1 else "├─"
                name = os.path.basename(f) if folder else f
                prefix = f"   {branch} " if folder else " "
                max_name = max(1, name_column - len(prefix))
                if len(name) > max_name:
                    name = name[: max_name - 1] + "…"
                pad = " " * max(2, name_column - len(prefix) - len(name))
                if injected:
                    stat_text = "injected" + (f" · {count}×" if count else "")
                    stat = c256(INJECTED, stat_text, bold=True)
                elif count:
                    stat_text = (
                        f"{self._heat_bar(heat, max_heat)} {count:>3}"
                        if browsing
                        else f"{self._heat_bar(heat, max_heat)} h{heat:>4.1f} · {count}×"
                    )
                    stat = c256(color, stat_text, bold)
                else:
                    stat = c256(DEAD, f"· {0:>3}")
                body.append(
                    c256(244 if folder else DIM, prefix) + c256(color, name, bold) + pad + stat
                )

        body_budget = max(1, budget)
        if len(body) > body_budget:
            hidden_extra = len(body) - body_budget
            body = body[:body_budget]
            body.append(c256(DEAD, f"   … {hidden_extra} files hidden"))
        if focus_summary:
            body.append(c256(DEAD, focus_summary))
        if not browsing and not body and not self.total_reads and not self.total_scans:
            body.extend(
                [
                    c256(WHITE, "  No discovery evidence yet.", bold=True),
                    c256(DIM, "  Work normally — reads and explicit searches light up here."),
                    c256(COOL, "  Want the loop now? Run /tt watch demo."),
                ]
            )

        lines = header + body
        lines.append("")
        lines.append(
            c256(DIM, " ")
            + c256(WHITE, f"{self.total_prompts}", bold=True)
            + c256(DIM, " prompts · ")
            + c256(WHITE, f"{self.total_reads}", bold=True)
            + c256(DIM, " reads · ")
            + c256(WHITE, f"{self.total_scans}", bold=True)
            + c256(DIM, " searches · ")
            + c256(WHITE, f"{self.total_skills}", bold=True)
            + c256(DIM, " skill uses · ")
            + c256(WHITE, f"{len(self.sessions)}", bold=True)
            + c256(DIM, " sessions")
        )
        lines.append(self._heat_legend(width))
        if browsing:
            icons = {"read": "●", "scan": "🔍", "skill": "⚡"}
            for e in self.buckets[self.selected]["events"][-3:]:
                who = "" if e["agent"] == "main" else f" [{e['agent']}]"
                stamp = (e["ts"] or "")[11:19]
                lines.append(c256(DIM, f"   {icons[e['t']]} {e['path']}{who} · {stamp}"))
        else:
            for ts, icon, path, agent in list(self.ticker)[:3]:
                age = now - ts
                agestr = (
                    "just now"
                    if age < 3
                    else (f"{age:.0f}s ago" if age < 60 else f"{age/60:.0f}m ago")
                )
                who = "" if agent in ("main", "prompt") else f" [{agent}]"
                fade = DIM if age < 8 else DEAD
                lines.append(c256(fade, f"   {icon} {path}{who} · {agestr}"))
        if browsing:
            lines.append(
                c256(DEAD, "   ← older prompt · → newer prompt · a live overview · q quit")
            )
        else:
            if self.last_event is None:
                beat = "listening for doc reads; searches and prompts appear as they arrive"
            else:
                age = now - self.last_event
                beat = (
                    "last event just now"
                    if age < 3
                    else (
                        f"last event {age:.0f}s ago"
                        if age < 60
                        else f"last event {age/60:.0f}m ago"
                    )
                )
            lines.append(c256(AMBER, self._sort_legend(width), bold=True))
            if tip_line:
                lines.append(tip_line)
            lines.append(c256(DEAD, f"   ←/→ prompts · q quit · {beat}"))
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
    if app.settings_open:
        if ch in ("s", "S", "\x1b"):
            app.settings_open = False
        elif ch in ("1", "2", "3"):
            app.set_prompt_mode({"1": "truncate", "2": "hash", "3": "off"}[ch])
        return False
    if ch in ("q", "Q"):
        return True
    if ch == "[":
        app.select_prev()
    elif ch == "]":
        app.select_next()
    elif ch in ("a", "A"):
        app.select_live()
    elif ch in ("f", "F"):
        app.set_sort("focus")
    elif ch in ("h", "H"):
        app.set_sort("hot")
    elif ch in ("c", "C"):
        app.set_sort("cold")
    elif ch in ("n", "N"):
        app.set_sort("name")
    elif ch in ("s", "S"):
        app.settings_open = True
        app.settings_message = ""
    return False


def demo_event(files, rng):
    hot = rng.sample(files, min(6, len(files)))  # a "task" keeps favoring a few files

    def gen():
        while True:
            roll = rng.random()
            if roll < 0.12:
                yield {
                    "t": "scan",
                    "path": rng.choice(["docs", "docs/development", "agents"]),
                    "session": "demo",
                    "agent": "main",
                }
            elif roll < 0.2:
                yield {
                    "t": "skill",
                    "skill": rng.choice(["doc-update", "insights", "tt"]),
                    "session": "demo",
                    "agent": "main",
                }
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
    ap.add_argument("--client", choices=("auto", "claude", "codex"), default="auto")
    args = ap.parse_args()

    app = App(inventory(), load_tips(detect_client(args.client)))
    tail = Tail(HIST)
    replay_events, replay_i = [], 0
    if args.replay:
        replay_events = load_all_events()
    else:
        for ev in iter_all_events():
            app.feed(ev, live=False)  # historic counts, no flashing
    rng = random.Random()
    demo = demo_event(app.files or ["CLAUDE.md"], rng) if args.demo else None
    next_evt = time.time() + 0.5
    next_inventory_sync = time.time() + INVENTORY_SYNC_SECS

    is_tty = sys.stdout.isatty()
    stdin_tty = sys.stdin.isatty()
    use_termios = stdin_tty and os.name != "nt"
    old_term = None
    if is_tty:
        # Full-screen TUI contract: private screen, no cursor, no line wrapping,
        # and no stale scrollback. Autowrap is restored in finally even on Ctrl+C.
        sys.stdout.write("\x1b[?1049h\x1b[?25l\x1b[?7l\x1b[2J\x1b[3J\x1b[H")
    if use_termios:  # pragma: no cover — needs a real tty
        import termios
        import tty

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
                if now >= next_inventory_sync:
                    app.sync_inventory(inventory())
                    next_inventory_sync = now + INVENTORY_SYNC_SECS
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
            sys.stdout.write("\x1b[?7h\x1b[?25h\x1b[?1049l")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
