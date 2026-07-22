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
