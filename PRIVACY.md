# Privacy Policy — trigger-tree

_Last updated: 2026-07-17_

## The short version

trigger-tree collects **no data**. Everything it records stays on your machine, in
your project directory, under your control. There are no network calls, no external
services, no analytics, and no dependencies that could introduce any.

## What the plugin records, and where

trigger-tree's hooks write a local event log to `$PROJECT/.trigger-tree/history.jsonl`
inside the project you use it in:

- **Documentation reads**: the relative path of files read by Read/Glob/Grep tool
  calls that match your configured documentation patterns, with a timestamp, session
  id, and agent type.
- **Skill invocations**: the name of invoked skills.
- **Prompt markers**: by default the first 200 characters of your prompt. This is
  configurable via `TT_LOG_PROMPTS` in `.trigger-tree/config.sh`:
  - `truncate` (default) — first 200 characters
  - `hash` — a SHA-1 digest only, no text
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
- No data leaves your machine.

## Retention and deletion

You own the data. Delete `.trigger-tree/` in your project at any time to remove all
recorded history. The directory is gitignored by the recommended setup, so it is not
committed or shared through version control.

## Changes and contact

Changes to this policy are recorded in this file's git history. Questions:
**me@heddevanderheide.nl**.
