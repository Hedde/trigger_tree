---
name: trigger-tree
description: Inspect and improve documentation discovery using trigger-tree's local telemetry. Use for trigger-tree status, live dashboard, heat/cold maps, documentation health, router suggestions, setup, or diagnostics.
---

# trigger-tree for Codex

Use the scripts under the plugin root. Resolve it by walking two directories up from this
`SKILL.md`. Keep output concise and never print raw telemetry unless requested.

- Status: run `python3 scripts/tt-stats.py` and summarize current heat, lifetime reads,
  untouched paths, and maturity.
- Live dashboard: run `scripts/tt-open.sh`, optionally with `demo` or `replay`.
- Insights: run `python3 scripts/tt-report.py` and link the generated local HTML report.
- Suggestions: run `python3 scripts/tt-suggestions.py` and return its output verbatim.
- Tips: run `python3 scripts/tt-tips.py --client codex` and return its output verbatim.
- Note: run `python3 scripts/tt-log.py note "<text>"`.
- Doctor: run `python3 scripts/tt-doctor.py` and return its diagnostics verbatim.
- Setup: run `python3 scripts/tt-setup.py`; pass `--prompt-mode truncate|hash|off`
  when requested. Explain that truncate stores the first 200 prompt characters locally.

Telemetry is collected silently by official Codex lifecycle hooks. Treat heat as decaying
current attention and lifetime reads as durable evidence. Untouched never means obsolete;
only mature datasets may identify guarded dead-path candidates.
