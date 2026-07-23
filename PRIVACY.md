# Privacy Policy — trigger-tree

_Last updated: 2026-07-19_

## The short version

trigger-tree sends **no data off your machine**. Its local telemetry stays in your
project directory, under your control. There are no network calls, external services,
analytics vendors, or runtime dependencies.

## What the plugin records, and where

trigger-tree's hooks write a local event log to `$PROJECT/.trigger-tree/history.jsonl`
inside the project you use it in:

- **Documentation activity**: relative paths read by Read, targeted by Glob/Grep,
  explicitly passed as existing doc paths to Bash `rg`/`grep`/`find` commands, or
  consumed by successful Bash `cat`/`head`/`tail`/non-mutating `sed`/`awk` calls.
  Bash reader arguments are checked after shell variables, substitutions, loops, and
  globs resolve; only matching normalized paths are retained, with event metadata.
- **Skill invocations**: the name of invoked skills.
- **Prompt markers**: before a project runs setup, only a short hash is stored —
  plugin installs are user-wide, and no repository records prompt text without
  its own explicit choice. Configurable via `TT_LOG_PROMPTS` in
  `.trigger-tree/config.sh`:
  - `hash` (the fallback before setup) — a SHA-1 digest only, no text
  - `truncate` (recommended during setup) — first 200 characters, local and gitignored
  - `off` — a bare marker, nothing else
- **Notes**: text you explicitly add with `/tt note`.

The optional HTML report (`/tt insights`) is generated locally to
`.trigger-tree/report.html`. If you choose to publish it as a Claude Artifact, that
is an explicit action you take through Claude Code — the plugin itself never uploads
anything.

## What the plugin does NOT do

- No network requests of any kind (the code is python3 standard library only — you
  can audit every line in this repository).
- No telemetry to the plugin author, Anthropic, or anyone else.
- Telemetry hooks store paths and event metadata, never documentation file contents.
  Local analysis commands read selected documentation and instruction content to derive
  routing, import, protection, and maintenance signals; that content is never copied into
  telemetry or uploaded.
- No shell commands, argument values other than matching documentation paths, search
  patterns, or Bash output are logged. Runtime wrappers pass stdout, stderr, and exit
  status through unchanged.
- No data leaves your machine.

## Retention and deletion

You own the data. Delete `.trigger-tree/` in your project at any time to remove all
recorded history. The directory is gitignored by the recommended setup, so it is not
committed or shared through version control.

## Changes and contact

Changes to this policy are recorded in this file's git history. Questions:
**me@heddevanderheide.nl**.
