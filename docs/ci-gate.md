# CI gate for documentation discoverability

`tt gate` scores **static discoverability** — repository structure only, no
telemetry, deterministic on every machine. Discoverable never means discovered:
what agents actually read stays local (`/tt insights`).

## What it measures

| Component | Weight | Meaning |
|---|---|---|
| routed | 40 | folder-router members actually listed in their entry point |
| linked | 30 | evaluable docs with at least one inbound link (no orphans) |
| entry points | 20 | doc folders with a `README.md`, `_index.md`, or `index.md` |
| watch scope | 10 | markdown files covered by `TT_WATCH_REGEX` |

Folders whose members are all `SKILL.md` files are skill packages and are not
required to have an entry point. Template files (`_*.md`) are never offenders.

## Usage

GitHub Actions (installs its own pinned version, runs inside your runner):

```yaml
- uses: Hedde/trigger_tree@v1.18.0
  with:
    min-score: "70"        # optional absolute floor
    badge: "discoverability.json"   # optional shields.io endpoint output
```

Any other CI:

```bash
pip install trigger-tree
tt gate --min-score 70
```

## Baseline (recommended): fail on regression, not on an arbitrary number

```bash
tt gate --update-baseline   # writes .trigger-tree/gate.json — commit it
```

With a committed baseline, the gate fails any change that lowers the score and
names the exact offending files with the edit that fixes them. Raising the bar is
deliberate: fix findings, re-run `--update-baseline`, commit. `/tt setup` keeps the
gitignore exception for `gate.json` in place.

## Exit codes

`0` pass · `1` gate failed (regression or below `--min-score`) · `2` usage or
execution error.
