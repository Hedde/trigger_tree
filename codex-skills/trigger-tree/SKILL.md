---
name: trigger-tree
description: Inspect and improve documentation discovery using trigger-tree's local telemetry. Use for trigger-tree status, live dashboard, heat/cold maps, documentation health, router suggestions, setup, or diagnostics.
---

# trigger-tree for Codex

Let `PLUGIN` be the plugin root: the directory two levels up from this `SKILL.md`.
**Always run the commands below from the user's project directory — never `cd` into
the plugin root** — and keep the `TT_PROJECT_DIR="$PWD"` prefix on every command, so
telemetry, dashboards, and reports bind to the project even though the scripts live
elsewhere. Keep output concise and never print raw telemetry unless requested.

- Status: run `TT_PROJECT_DIR="$PWD" python3 "$PLUGIN/scripts/tt-stats.py" --client codex` and summarize current heat, lifetime reads,
  untouched paths, and maturity.
- Live dashboard: run `TT_PROJECT_DIR="$PWD" TT_CLIENT=codex "$PLUGIN/scripts/tt-open.sh"`, optionally with `demo` or
  `replay`, so the detached dashboard watches this project and loads only Codex-specific tips.
- Insights: run `TT_PROJECT_DIR="$PWD" python3 "$PLUGIN/scripts/tt-report.py" --client codex` and link the generated local HTML report.
- Suggestions: run `TT_PROJECT_DIR="$PWD" python3 "$PLUGIN/scripts/tt-suggestions.py"` and return its output verbatim.
- Badge: run `TT_PROJECT_DIR="$PWD" python3 "$PLUGIN/scripts/tt-stats.py" --client codex --badge` and return the written path.
- Gate: run `TT_PROJECT_DIR="$PWD" python3 "$PLUGIN/scripts/tt-gate.py"` and return its output verbatim.
- Tips: run `TT_PROJECT_DIR="$PWD" python3 "$PLUGIN/scripts/tt-tips.py" --client codex` and return its output verbatim.
- Note: run `TT_PROJECT_DIR="$PWD" python3 "$PLUGIN/scripts/tt-log.py" note "<text>"`.
- Doctor: run `TT_PROJECT_DIR="$PWD" python3 "$PLUGIN/scripts/tt-doctor.py"` and return its diagnostics verbatim.
- Setup: ask for `truncate` (recommended; first 200 prompt characters stored locally),
  `hash` (no prompt text), or `off` (marker only), then pass the answer explicitly as
  `TT_PROJECT_DIR="$PWD" python3 "$PLUGIN/scripts/tt-setup.py" --prompt-mode truncate|hash|off`.
- Uninstall: run `TT_PROJECT_DIR="$PWD" python3 "$PLUGIN/scripts/tt-uninstall.py"`; explain that telemetry and ignore
  entries remain until the user explicitly deletes them.

Telemetry is collected silently by official Codex lifecycle hooks. Treat heat as decaying
current attention and lifetime reads as durable evidence. Untouched never means obsolete;
only mature datasets may identify guarded dead-path candidates. Exclude retired paths from
current rankings, treat folder routers as routers rather than templates, and keep any insights
summary to at most 15 lines.
