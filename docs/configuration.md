# Configuration

`/tt setup` creates `.trigger-tree/config.sh`. Every key resolves in three
layers — bundled plugin default, then the user-wide `~/.trigger-tree/config.sh`
(location overridable via `TT_USER_CONFIG`), then the project file — and the
project always wins. The user layer exists so one person can set a default such
as `TT_LOG_PROMPTS='off'` for every repository before any project has run setup;
`tt doctor` reports the effective prompt mode and which layer selected it.

| Variable | Default | Meaning |
|---|---|---|
| `TT_WATCH_REGEX` | docs/agents/skills/briefs plus root `CLAUDE.md`, `AGENTS.md`, and `GEMINI.md` | Documentation reads to count |
| `TT_SCOPE_IGNORE` | empty | comma-separated globs acknowledging intentionally unwatched markdown; leaves gate findings, SARIF, and the watch-scope denominator |
| `TT_SCAN_REGEX` | documentation folders | Search targets to count |
| `TT_ALWAYS_LOADED_REGEX` | `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, guidance, and skills | Context excluded from cold-path review |
| `TT_CRITICAL_GLOB` | empty | Comma-separated rare-but-critical paths |
| `TT_LOG_PROMPTS` | `hash` | `truncate`, `hash`, or `off` for future prompt text/fingerprints; setup recommends `truncate` per project |
| `TT_LOG_TOPICS` | `off` | `on` stores at most eight matched labels from a repository-bounded vocabulary; no free prompt text |
| `TT_LOG_COMMANDS` | `off` | `classified` stores matched manifest pattern IDs only; `full` also stores a bounded command line; output is never stored |
| `TT_LOG_AGENTS` | `off` | `on` stores the persona name of a launched subagent; the task prompt and description are never read |
| `TT_EDIT_REGEX` | matches nothing | Regex selecting in-project edit paths for adherence; events contain path and tool only |
| `TT_ROTATE_BYTES` | 5 MB | History rotation threshold |
| `TT_EXPERIMENTAL_OUTCOMES` | `off` | Local correlational committed/abandoned view |

For a new project, interactive setup asks for the prompt mode and recommends `truncate`;
Enter accepts it. Setup also writes the optional adherence capture choices explicitly:
topics, classified commands, and a conservative project-relative edit scope. Existing
installs that have no new keys remain off and never start recording more silently.
Piped, hook, and CI runs cannot block on the question and use privacy-preserving
defaults. Existing project choices are preserved unless their explicit options are
passed. Setup also reports watch coverage and can propose a regex, but never applies it
without `tt-setup.py --apply-watch-suggestion`. `/tt doctor` fails on zero watch matches,
warns on very low coverage, and identifies manifest probes that cannot fire under current
capture.

`TT_LOG_TOPICS` is independent of `TT_LOG_PROMPTS`: topic matching behaves identically
in `truncate`, `hash`, and `off` modes. The vocabulary comes only from router labels and
manifest topics, matching case-insensitive whole words, capped at eight. Topic events can
include a manifest fingerprint so evidence from a different vocabulary is not treated as
negative evidence.

`TT_LOG_COMMANDS=classified` records an array such as
`"matched":["run-checks"]`, never the original command. `full` is a separate, explicit
privacy choice and still never records stdout or stderr. `TT_EDIT_REGEX` can widen
measurement beyond documentation; use the narrowest project-relative paths needed by
`command_after_edit` and `path_avoided` probes. External and escaping paths are rejected,
and edit content and diffs are never recorded.

All three root instruction conventions are watchable for consistent event handling,
but they are classified as injected/always loaded and excluded from untouched review.
`index.md` remains a normal folder router; it has no Gemini-specific classification.

External local tools can ingest a validated event with `python3 <plugin>/scripts/tt-log.py ingest '{"t":"read","path":"docs/design/index.md"}'`. Invalid events are dropped silently.

## Publishing the docs-health badge

Run `/tt badge` (or `python3 scripts/tt-stats.py --badge`) to write a shields.io endpoint at `.trigger-tree/badge.json`. Because telemetry stays local and is gitignored, a normal CI checkout cannot calculate this grade. From the measured development checkout, run `make badge-publish` to update only `docs-health.json` on an existing `badges` branch while preserving its other endpoints.

```markdown
[![docs health](https://img.shields.io/endpoint?url=https%3A%2F%2Fraw.githubusercontent.com%2FOWNER%2FREPO%2Fbadges%2Fdocs-health.json)](docs/heat-model.md)
```

CI independently updates `coverage.json` on the same branch and preserves the locally published docs-health value. Before measurement is mature, the public badge deliberately says `measuring…`. Publishing is explicit because it pushes local aggregate evidence to the repository; file paths and event history are never included in the badge payload.
