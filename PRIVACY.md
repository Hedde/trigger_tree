# Privacy Policy — trigger-tree

_Last updated: 2026-07-27_

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
- **Optional bounded topics**: with `TT_LOG_TOPICS='on'`, at most eight
  case-insensitive whole-word labels selected from the repository's own router and
  directive-manifest vocabulary. No prompt-derived free text is stored, and this works
  independently of the prompt mode.
- **Optional edits**: paths matching `TT_EDIT_REGEX`, normalized relative to the
  project, plus tool name and event metadata. External paths, file content, arguments,
  diffs, and patches are not stored.
- **Optional agent names**: `TT_LOG_AGENTS='on'` stores the persona name of a
  launched subagent (for example `backend-engineer`). The launch payload also
  carries the task prompt and description; trigger-tree never reads either.
- **Optional commands**: `TT_LOG_COMMANDS='classified'` stores only stable IDs of
  user-confirmed manifest patterns that matched. `full` additionally stores a bounded
  command line. Command output is never stored. Missing configuration means off.
- **Test and commit boundaries**: test pass/fail status and an observable local
  `git commit` command, used only to order deterministic probes; no test output or commit
  message is retained by those events.
- **Prompt markers**: before a project runs setup, only a short hash is stored —
  plugin installs are user-wide, and no repository records prompt text without
  its own explicit choice. Configurable via `TT_LOG_PROMPTS` in
  `.trigger-tree/config.sh`:
  - `hash` (the fallback before setup) — a SHA-1 digest only, no text; a
    user-wide `~/.trigger-tree/config.sh` can set `off` as the pre-setup
    default for every repository, and the project's own choice always wins
  - `truncate` (recommended during setup) — first 200 characters, local and gitignored
  - `off` — a bare marker, nothing else
- **Notes**: text you explicitly add with `/tt note`.

The committed `.trigger-tree/directives.json` is not telemetry. It is
human-readable configuration containing instruction file paths and SHA-256 hashes,
source line references, optional directive text, and user-confirmed deterministic
probes. A model may propose this file only at authoring time; the user confirms it and
measurement thereafter uses no model tokens.

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
- With command capture off or classified, no shell command line is logged. Explicit
  `full` mode stores a bounded command line locally; command output, search output, and
  MCP responses are never logged. Runtime wrappers pass stdout, stderr, and exit status
  through unchanged.
- No data leaves your machine.

## Retention and deletion

You own the data. Delete `.trigger-tree/` in your project at any time to remove all
recorded history. The directory is gitignored by the recommended setup, so it is not
committed or shared through version control.

## Changes and contact

Changes to this policy are recorded in this file's git history. Questions:
**me@heddevanderheide.nl**.
