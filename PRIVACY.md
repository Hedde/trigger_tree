# Privacy Policy — trigger-tree

_Last updated: 2026-07-18_

## The short version

trigger-tree sends **no data off your machine**. Its local telemetry stays in your
project directory, under your control. There are no network calls, external services,
analytics vendors, or runtime dependencies.

## What the plugin records, and where

trigger-tree's hooks write a local event log to `$PROJECT/.trigger-tree/history.jsonl`
inside the project you use it in:

- **Documentation activity**: relative paths read by Read, targeted by Glob/Grep,
  or explicitly passed as existing doc paths to Bash `rg`/`grep`/`find` commands,
  with a timestamp, session id, and agent type.
- **Skill invocations**: the name of invoked skills.
- **Prompt markers**: by default a short SHA-1 hash with no prompt text. This is
  configurable via `TT_LOG_PROMPTS` in `.trigger-tree/config.sh`:
  - `hash` (default) — a SHA-1 digest only, no text
  - `truncate` (explicit opt-in) — first 200 characters
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
- No reading of file *contents* — only paths and event metadata are logged.
- No shell commands, search patterns, or Bash output are logged — only a normalized
  explicit documentation target path.
- No data leaves your machine.

## Retention and deletion

You own the data. Delete `.trigger-tree/` in your project at any time to remove all
recorded history. The directory is gitignored by the recommended setup, so it is not
committed or shared through version control.

## Changes and contact

Changes to this policy are recorded in this file's git history. Questions:
**me@heddevanderheide.nl**.
