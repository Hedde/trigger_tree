# 🌳 trigger-tree

<p align="center"><img src="https://raw.githubusercontent.com/Hedde/trigger_tree/main/assets/trigger-tree-logo.png" alt="trigger-tree logo" width="160"></p>

> **See which project docs your AI actually discovers.**

[![CI](https://github.com/Hedde/trigger_tree/actions/workflows/ci.yml/badge.svg)](https://github.com/Hedde/trigger_tree/actions/workflows/ci.yml) [![coverage](https://img.shields.io/endpoint?url=https%3A%2F%2Fraw.githubusercontent.com%2FHedde%2Ftrigger_tree%2Fbadges%2Fcoverage.json)](https://github.com/Hedde/trigger_tree/actions/workflows/ci.yml) [![release](https://img.shields.io/github/v/release/Hedde/trigger_tree?label=release)](https://github.com/Hedde/trigger_tree/releases/latest) [![PyPI](https://img.shields.io/pypi/v/trigger-tree?label=pypi)](https://pypi.org/project/trigger-tree/) [![platforms](https://img.shields.io/badge/platforms-macOS%20·%20Linux%20·%20Windows-lightgrey.svg)](docs/platform-support.md) [![docs discoverability](https://img.shields.io/endpoint?url=https%3A%2F%2Fraw.githubusercontent.com%2FHedde%2Ftrigger_tree%2Fbadges%2Fdocs-discoverability.json)](docs/ci-gate.md) [![docs health](https://img.shields.io/endpoint?url=https%3A%2F%2Fraw.githubusercontent.com%2FHedde%2Ftrigger_tree%2Fbadges%2Fdocs-health.json)](docs/heat-model.md)

<p align="center"><a href="https://hedde.github.io/trigger_tree/"><img src="https://raw.githubusercontent.com/Hedde/trigger_tree/main/docs/assets/demo.gif" alt="Real terminal recording of the live trigger-tree dashboard: doc reads pulse through the tree, sorting, prompt browsing, and the privacy settings panel" width="900"></a></p>

- Local and dependency-free: no cloud, analytics, or model tokens.
- Separate heat, lifetime reads, searches, and untouched paths instead of guessing intent.
- Reduce the evidence to an A–F documentation health grade when detail is unnecessary.

Documentation steers an AI coding assistant toward your team’s patterns and guardrails. But **a rule that is never read protects nothing**. trigger-tree records discovery evidence so you can improve the routes without pretending a read proves understanding.

## Quick start

| Claude Code | Codex |
|---|---|
| `/plugin marketplace add Hedde/trigger_tree`<br>`/plugin install trigger-tree@trigger-tree`<br>`/reload-plugins`<br>`/tt watch demo`<br>`/tt setup` · `/tt doctor`<br>Work normally, then `/tt insights` | `codex plugin marketplace add Hedde/trigger_tree`<br>`codex plugin add trigger-tree@trigger-tree`<br>Restart Codex<br>Ask it to run `python3 "$PLUGIN_ROOT/scripts/tt-watch.py" --demo`<br>Use the bundled trigger-tree skill for setup, doctor, and insights |

The Claude `/tt` skill is explicitly user-triggered. Codex installs the equivalent skill and lifecycle hooks through its plugin marketplace.

Prefer a standalone CLI — for CI, git-hook ingestion, or dashboards without a plugin?
`pipx install trigger-tree` (or `uvx --from trigger-tree tt`), then `tt doctor`, `tt watch --demo`, `tt stats`.

Before a project runs setup, prompt logging stores only a short hash — plugin
installs are user-wide, so no repository records prompt text without its own
explicit choice. `/tt setup` asks per project: `truncate` (recommended,
recognizable 200-character previews), `hash`, or `off`.

## Who gets what?

| You are… | trigger-tree gives you… |
|---|---|
| Senior developer | File/folder heat, search evidence, router gaps, and prompt-level browsing |
| Tech lead | Trends, task clusters, protected-context review, and evidence-backed fixes |
| Product owner | One honest A–F docs-health signal, provisional until measurement matures |

## Commands

| Command | Result |
|---|---|
| `/tt watch demo` | Instant synthetic dashboard; no telemetry required |
| `/tt setup [truncate\|hash\|off]` | Wire the repo and choose prompt privacy |
| `/tt doctor` | Check hooks, liveness, scope, privacy, and statusline wiring |
| `/tt status` | Current heat, lifetime reads, and untouched paths |
| `/tt watch` | Live mock-TUI dashboard with prompt browsing and sorting |
| `/tt insights` | Deterministic analysis plus a local HTML report |
| `/tt suggestions` | Up to five evidence-backed routing improvements |
| `/tt badge` | Write a public-safe docs-health endpoint JSON |
| `/tt note <text>` | Add a local timeline annotation |
| `/tt gate` | Deterministic discoverability score; gate CI on regressions |
| `/tt uninstall` | Remove wiring without deleting telemetry |

Search telemetry is a conservative lower bound; see [measurement boundaries](docs/heat-model.md).

## How it works

1. **Hooks log shell-side** to the gitignored `.trigger-tree/history.jsonl`; failures never interrupt the coding session.
2. **A deterministic aggregator computes every metric** with Python’s standard library; the model interprets but never counts.
3. **Discovery remains model-driven**: trigger-tree measures your routers and reads without injecting context or changing routing.

## Gate your CI on discoverability

The gate scores repository structure only — router coverage, orphaned docs, folder
entry points, watch scope — so it is deterministic, needs no telemetry, and uploads
nothing. Discoverable never means discovered; read telemetry stays local.

```yaml
- uses: Hedde/trigger_tree@v1.21.0   # or: pip install trigger-tree && tt gate
```

Commit a baseline once with `tt gate --update-baseline` and every PR that makes your
docs harder to discover fails with the exact file and fix. Findings export as
SARIF for code-scanning annotations. The gate checks the wiring, not the words: whether your `CLAUDE.md` actually
instructs agents to follow the routers is proven by local telemetry, not by the
gate. Boundaries and details: [CI gate](docs/ci-gate.md).

## Where it fits

| Category | Question answered |
|---|---|
| Token/trace observability (Langfuse, Arize, W&B) | What did the model call, spend, and produce? |
| Documentation linters | Is documentation structurally or stylistically valid? |
| trigger-tree | Which local project docs did the coding assistant actually discover? |

The categories complement each other. trigger-tree does not evaluate answer quality or claim that a read caused an outcome.

## Learn more

[Documentation router](docs/README.md) · [Dashboard](docs/dashboard.md) · [Heat model](docs/heat-model.md) · [Configuration](docs/configuration.md) · [Privacy](docs/privacy.md) · [Glossary](docs/glossary.md) · [FAQ](docs/faq.md) · [Website](https://hedde.github.io/trigger_tree/) · [Changelog](CHANGELOG.md)

MIT © Hedde van der Heide
