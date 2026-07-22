# Configuration

`/tt setup` creates `.trigger-tree/config.sh`.

| Variable | Default | Meaning |
|---|---|---|
| `TT_WATCH_REGEX` | docs/agents/skills/briefs plus root guidance | Documentation reads to count |
| `TT_SCAN_REGEX` | documentation folders | Search targets to count |
| `TT_ALWAYS_LOADED_REGEX` | guidance and skills | Context excluded from cold-path review |
| `TT_CRITICAL_GLOB` | empty | Comma-separated rare-but-critical paths |
| `TT_LOG_PROMPTS` | `truncate` after setup | `truncate`, `hash`, or `off` for future prompts |
| `TT_ROTATE_BYTES` | 5 MB | History rotation threshold |
| `TT_EXPERIMENTAL_OUTCOMES` | `off` | Local correlational committed/abandoned view |

Setup reports watch coverage and can propose a regex, but never applies it without `tt-setup.py --apply-watch-suggestion`. `/tt doctor` fails on zero matches and warns on very low coverage.

External local tools can ingest a validated event with `python3 <plugin>/scripts/tt-log.py ingest '{"t":"read","path":"docs/design/index.md"}'`. Invalid events are dropped silently.

## Publishing the docs-health badge

Run `/tt badge` (or `python3 scripts/tt-stats.py --badge`) to write a shields.io endpoint at `.trigger-tree/badge.json`. Publish that file as `docs-health.json` on a `badges` branch, then embed:

```markdown
[![docs health](https://img.shields.io/endpoint?url=https%3A%2F%2Fraw.githubusercontent.com%2FOWNER%2FREPO%2Fbadges%2Fdocs-health.json)](docs/heat-model.md)
```

The CI workflow in this repository shows the complete orphan-branch publishing pattern alongside its coverage endpoint. Before measurement is mature, the public badge deliberately says `measuring…`.
