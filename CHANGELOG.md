# Changelog

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
