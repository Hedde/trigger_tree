# Changelog

## 0.5.3 — 2026-07-17

- **Fix: both arrow keys browsed backwards.** The key loop mixed `select()` on
  the raw fd with buffered `sys.stdin.read()`: the buffered read slurped the
  whole escape sequence, the follow-up `select()` saw an empty fd, and the
  leftover `[` replayed on the *next* keypress — so ← and → both acted as
  "prev", one press late. Keys are now read raw via `os.read()` (`read_key()`),
  with a pipe-based regression test.

## 0.5.2 — 2026-07-17

- **Arrow keys** now browse prompts too (←/→ on macOS/Linux escape sequences and
  Windows console codes), and the hint lines say so in plain words
  ("←/→ browse per prompt"). Fixes a truncation assertion in the 0.5.1 test run.
- **Bounded prompt detail**: the browser keeps the last 20 prompts (500 events
  each) while dashboard totals keep aggregating the full history — endless
  sessions can't grow memory.
- **Website demo** now demonstrates per-prompt browsing with ←/→ as well.

## 0.5.1 — 2026-07-17

- **Typed prompts are now instantly visible in the live view**: every prompt
  appears in the ticker (`▸ "…"`) the moment you hit enter, and the footer counts
  prompts alongside reads — so "5 prompts · 0 reads" self-explains an
  injected-context session instead of looking stale.

## 0.5.0 — 2026-07-17

- **Per-prompt browsing in the dashboard**: `[` and `]` step through every typed
  prompt; the tree filters to exactly what that input aggregated (reads, scans,
  skill uses) with the prompt text in the header; `a` returns to live. Reads
  before the first prompt land in a "(session start)" bucket.
- **End-to-end regression guard**: a test now spawns the watcher and the logger as
  separate processes (exactly how real hooks write) and asserts the live tail
  picks the events up — the "is it updating?" question is CI-proven forever.

## 0.4.2 — 2026-07-17

- **Liveness heartbeat** in the dashboard hint line: "live · last event 12s ago",
  or "listening for doc reads (injected context never shows here)" when nothing
  has arrived yet — answers "is it stale or is nothing happening?" at a glance.

## 0.4.1 — 2026-07-17

- Launcher pane messages now explain exit causes: SIGTERM/SIGINT (e.g. an external
  `kill`) reads "terminated from outside — not a crash" instead of a bare status
  code; real crashes say "crashed". Ends the status-143 confusion.

## 0.4.0 — 2026-07-17

- **External ingestion adapter**: `tt-log.py ingest '<event-json>'` — a stable,
  validated entry point so any tool (a Codex wrapper, a git hook, an editor
  plugin) can append telemetry to the same history. Missing ts/session stamped,
  invalid events dropped silently. Completes the plugin side of multi-tool support.

## 0.3.7 — 2026-07-17

- `/tt watch` confirmation line now prints the running plugin version
  ("trigger-tree v0.3.7 watcher opened …") so a stale session cache is instantly
  visible. FAQ entry added for the flash-and-disappear symptom (stale pre-v0.3.3
  cache → `/reload-plugins`).

## 0.3.6 — 2026-07-17

- **Positioning, research-backed**: README and site now state the validated gap —
  agent observability tools measure tokens/traces, none measure per-task doc reads;
  Anthropic's guidance says to prune CLAUDE.md but nothing validates the pruning;
  the Fallow analogy (unused code → unused docs). Added a who-is-it-for table and
  an honest Limitations section (official-plugin convention).

## 0.3.5 — 2026-07-17

- **Branding: lowercase everywhere.** The plugin now presents itself as
  `trigger-tree` across README, website, dashboard banner, SKILL, report and
  manifests — matching the naming convention of official Claude Code plugins
  (`commit-commands`, `security-guidance`, …). The `/tt` command is unchanged.

## 0.3.4 — 2026-07-17

- **Stability: layered, crash-proof config resolution** in all scripts (project
  override → plugin default → hardcoded; broken regexes skipped). Fixes the
  instant-crash of `/tt watch` in projects with a partial `.trigger-tree/config.sh`.
- **Multi-session safe splits**: the iTerm2 split now targets the exact session
  that invoked it (via `ITERM_SESSION_ID`) — two Claude sessions in different
  projects each get their own split, never the frontmost window by accident.
- **Discovery-structure awareness**: folders without an entry point are flagged
  ("no index file") and `/tt suggestions` proposes adding one; `_template.md`-style
  files are auto-classified as intentional archive; nested `CLAUDE.md`/
  `CLAUDE.local.md` files count as always-loaded (they inject on demand and are
  invisible to read-telemetry — per official memory docs).
- **README/site**: layman-first hero, "Why measure documentation?" and a sourced
  "Structuring your docs for discovery" guide; site now has six feature cards and
  a "Why this matters" section.

## 0.3.3 — 2026-07-17

- **Fix: iTerm2 split closed instantly.** iTerm2's AppleScript `command` parameter
  is exec-style (no shell), so the compound `cd … && …` command died on launch.
  The split now runs a generated launcher script (shebang + shell), which also
  keeps the pane open with the error message if the watcher ever exits non-zero.

## 0.3.2 — 2026-07-17

- **Dashboard visual parity with the website demo**: three-tier heat palette
  (green → amber → red), clean folder lines (untouched counters only appear when
  files are collapsed), "just now" ticker, dim `q quit` hint line.
- **Documentation health grade**: deterministic A–F score (coverage, router gaps,
  hunting ratio) in stats, `/tt status`, `/tt insights` and as hero card in the
  HTML report — one number a product owner can track sprint over sprint.

## 0.3.1 — 2026-07-17

- `/tt watch` on macOS now stays in the terminal you called it from: iTerm2 users
  get a split pane in the current window (detected via `TERM_PROGRAM`), with a
  new-window fallback; Terminal.app remains the fallback for everything else.

## 0.3.0 — 2026-07-17

- **Windows support**: posix path normalization, utf-8 everywhere, ANSI console
  enable + msvcrt keys in the dashboard, `wt.exe`/`start` launcher branch,
  `python3||python` fallbacks. CI test matrix now runs ubuntu + macos + windows.
- **Folder heat & cold map**: per-folder coverage and read volume in stats and the
  HTML report.
- **Router-gap detection**: untouched files are cross-referenced against all docs —
  "untouched and unreferenced" pinpoints where the router is blind.
- **`/tt suggestions`**: max 5 prioritized, evidence-backed router fixes, applied
  only after confirmation.
- **README overhaul** (hero, how-it-works with hook transparency, FAQ, platform
  matrix) and a **website** at hedde.github.io/trigger_tree — an interactive
  recreation of the live dashboard, with a few easter eggs for the curious.

## 0.2.1 — 2026-07-17

- Rename plugin id `tt` → `trigger-tree` for the plugin directory (unique, descriptive
  name). The `/tt` command is unchanged — it comes from the root skill's `name` field.
- GitHub Pages docs site: https://hedde.github.io/trigger_tree/

## 0.2.0 — 2026-07-17

- **Skill-tool telemetry**: PostToolUse hook on `Skill` logs skill invocations; an
  invoked skill's SKILL.md counts as touched, shrinking the `always_loaded` blind spot.
- **Portability**: logger and statusline rewritten in pure python3 (jq and BSD `date`
  dependencies dropped); `/tt watch` opens a tmux split, macOS Terminal, or
  gnome-terminal/konsole/xterm.
- **Prompt privacy**: `TT_LOG_PROMPTS=truncate|hash|off` — fingerprints keep working
  in all modes.
- **Log rotation**: history.jsonl rotates to timestamped archives beyond
  `TT_ROTATE_BYTES` (default 5 MB); aggregator and watcher read all archives.
- **Trend + annotations**: daily/weekly reads-scans buckets with hunting ratio;
  `/tt note <text>` marks router changes on the timeline so their effect is visible.
- **Task clusters**: fingerprints grouped by Jaccard similarity (≥ 0.6) instead of
  exact-set matching.
- **`/tt setup`**: idempotent project wiring (gitignore, statusline copy +
  registration, optional config override).
- **CI**: unit + smoke tests with an 80% coverage gate, shellcheck,
  `claude plugin validate`. Measured coverage is published as a live badge
  (shields endpoint JSON on the `badges` branch — no external coverage service).
- **Community files**: CONTRIBUTING, code of conduct, security policy, issue/PR
  templates, README badges.

## 0.1.0 — 2026-07-17

Initial release.

- Telemetry hooks (SessionStart, UserPromptSubmit, PostToolUse on Read|Glob|Grep) →
  `.trigger-tree/history.jsonl`, shell-side, zero model tokens.
- `/tt` root skill with subcommands: `status`, `watch [demo|replay]`, `insights`, `help`.
- Live ASCII pulse dashboard (`tt-watch.py`): heat-colored doc tree, white flash +
  upward ripple per read, hunting ticker, subagent attribution.
- Deterministic aggregator (`tt-stats.py`): per-file read counts, task fingerprints,
  co-read pairs, hunting, untouched paths with a maturity model
  (cold-start → warming → mature).
- Self-contained HTML report (`tt-report.py`), published via Artifact from `/tt insights`.
- Statusline script with age-based pulse dot (ships with the plugin; registered per
  project).
