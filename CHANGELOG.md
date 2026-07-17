# Changelog

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
- **CI**: smoke test over a fixture project, shellcheck, `claude plugin validate`.

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
