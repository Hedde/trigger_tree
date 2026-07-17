# Changelog

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
