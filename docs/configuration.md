# Configuration

`/tt setup` creates `.trigger-tree/config.sh`.

| Variable | Default | Meaning |
|---|---|---|
| `TT_WATCH_REGEX` | docs/agents/skills/briefs plus root `CLAUDE.md`, `AGENTS.md`, and `GEMINI.md` | Documentation reads to count |
| `TT_SCOPE_IGNORE` | empty | comma-separated globs acknowledging intentionally unwatched markdown; leaves gate findings, SARIF, and the watch-scope denominator |
| `TT_SCAN_REGEX` | documentation folders | Search targets to count |
| `TT_ALWAYS_LOADED_REGEX` | `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, guidance, and skills | Context excluded from cold-path review |
| `TT_CRITICAL_GLOB` | empty | Comma-separated rare-but-critical paths |
| `TT_LOG_PROMPTS` | `truncate` | `truncate`, `hash`, or `off` for future prompts |
| `TT_ROTATE_BYTES` | 5 MB | History rotation threshold |
| `TT_EXPERIMENTAL_OUTCOMES` | `off` | Local correlational committed/abandoned view |

For a new project, interactive setup asks for the prompt mode and recommends `truncate`; Enter accepts it. Piped, hook, and CI runs cannot block on the question and use the same default. Existing project choices are preserved unless `--prompt-mode` is explicit. Setup also reports watch coverage and can propose a regex, but never applies it without `tt-setup.py --apply-watch-suggestion`. `/tt doctor` fails on zero matches and warns on very low coverage.

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
