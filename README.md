# 🌳 trigger-tree

<p align="center"><img src="https://raw.githubusercontent.com/Hedde/trigger_tree/main/assets/trigger-tree-logo.png" alt="trigger-tree logo" width="160"></p>

> **Gate documentation discovery in CI. Measure whether your project instructions change what agents do.**

[![CI](https://github.com/Hedde/trigger_tree/actions/workflows/ci.yml/badge.svg)](https://github.com/Hedde/trigger_tree/actions/workflows/ci.yml) [![coverage](https://img.shields.io/endpoint?url=https%3A%2F%2Fraw.githubusercontent.com%2FHedde%2Ftrigger_tree%2Fbadges%2Fcoverage.json)](https://github.com/Hedde/trigger_tree/actions/workflows/ci.yml) [![release](https://img.shields.io/github/v/release/Hedde/trigger_tree?label=release)](https://github.com/Hedde/trigger_tree/releases/latest) [![PyPI](https://img.shields.io/pypi/v/trigger-tree?label=pypi)](https://pypi.org/project/trigger-tree/) [![platforms](https://img.shields.io/badge/platforms-macOS%20·%20Linux%20·%20Windows-lightgrey.svg)](docs/platform-support.md) [![docs discoverability](https://img.shields.io/endpoint?url=https%3A%2F%2Fraw.githubusercontent.com%2FHedde%2Ftrigger_tree%2Fbadges%2Fdocs-discoverability.json)](docs/ci-gate.md) [![docs health](https://img.shields.io/endpoint?url=https%3A%2F%2Fraw.githubusercontent.com%2FHedde%2Ftrigger_tree%2Fbadges%2Fdocs-health.json)](docs/heat-model.md)

Two concrete offers:

1. **CI gate — immediate.** A deterministic, telemetry-free structural check fails a
   PR with the affected file and a suggested fix.
2. **Instruction adherence — after a few working sessions.** See whether an applicable
   `CLAUDE.md` directive was followed by observable behavior, and what that always-loaded
   instruction costs on every request.

Heat maps and the A–F documentation-health grade add longer-term discovery evidence.
Everything runs locally with Python’s standard library: no cloud, analytics, network
calls, or model tokens while measuring.

<p align="center"><a href="https://hedde.github.io/trigger_tree/"><img src="https://raw.githubusercontent.com/Hedde/trigger_tree/main/docs/assets/demo.gif" alt="Real terminal recording of the live trigger-tree dashboard: doc reads pulse through the tree, sorting, prompt browsing, and the privacy settings panel" width="900"></a></p>

## Gate your CI on discoverability

The gate scores repository structure only — router coverage, orphaned docs, folder
entry points, and watch scope — so it works on day one without telemetry.

```yaml
- uses: Hedde/trigger_tree@v1.25.0   # or: pip install trigger-tree && tt gate
```

Commit a baseline once with `tt gate --update-baseline`. A regression then fails the PR
with the exact file and fix. SARIF and GitLab Code Quality exports are available in
[examples/](examples/). The gate checks wiring, not wording; see [CI gate](docs/ci-gate.md).

## Does your CLAUDE.md actually work?

Injected instructions are always loaded, so another read counter cannot answer this.
trigger-tree asks a narrower, measurable question: **when a directive applied, did its
declared probe observe the behavior it requested?**

| Directive | Opportunities | Followed | Rate | Confidence |
|---|---:|---:|---:|---|
| Route telemetry questions to `docs/heat-model.md` | 8 | 7 | 88% | warming |
| Run checks before committing | 6 | 5 | 83% | warming |
| Preserve stdlib-only runtime code | — | — | — | unobservable |

> Your always-loaded context is ~190 tokens per session. 2 directives (~34 tokens)
> have not been triggered in 12 sessions over 9.8 days.

The table is representative output. A committed, reviewable manifest defines each
probe; the model may propose it once, but you confirm it and deterministic local code
does every count thereafter. **Unobserved means evidence was not captured; it does not
mean violated.** Zero opportunities is `never-triggered`, a review prompt rather than
a removal recommendation. See [instruction adherence](docs/instruction-adherence.md).

## Honest time to value

| Capability | When it becomes useful |
|---|---|
| CI discoverability gate | Immediately; no telemetry required |
| Instruction adherence | After at least 5 applicable opportunities, usually a few working sessions; earlier rates are provisional |
| Heat and documentation health | Directional during warm-up; strongest after roughly a month of normal work |

## Quick start

**Claude Code**

```text
/plugin marketplace add Hedde/trigger_tree
/plugin install trigger-tree@trigger-tree
/reload-plugins
/tt watch demo
/tt setup
/tt doctor
```

Work normally, then `/tt insights`.

**Codex**

```text
codex plugin marketplace add Hedde/trigger_tree
codex plugin add trigger-tree@trigger-tree
```

Restart Codex and, when it shows **Hooks need review**, choose **Trust all and
continue** — Codex silently skips untrusted hooks, and non-interactive
`codex exec` runs never persist trust, so telemetry stays empty until the four
hooks are trusted in the TUI. Repeat the review after an upgrade that changes a
hook. Then ask Codex to run `python3 "$PLUGIN_ROOT/scripts/tt-watch.py" --demo`;
the bundled trigger-tree skill covers setup, doctor, and insights.

The Claude `/tt` skill is explicitly user-triggered. Codex installs the equivalent skill and lifecycle hooks through its plugin marketplace.

Prefer a standalone CLI — for CI, git-hook ingestion, or dashboards without a plugin?
`pipx install trigger-tree` (or `uvx --from trigger-tree tt`), then `tt doctor`, `tt watch --demo`, `tt stats`.

Before a project runs setup, prompt logging stores only a short hash — plugin
installs are user-wide, so no repository records prompt text without its own
explicit choice. A user-wide default in `~/.trigger-tree/config.sh` (for
example `TT_LOG_PROMPTS='off'`) tightens that for every repository at once;
`/tt setup` still asks per project — `truncate` (recommended, recognizable
200-character previews), `hash`, or `off` — and the project choice wins.

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
| `/tt instructions` | Per-directive adherence, uncertainty, and always-loaded cost |
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

## Where it fits

| Category | Question answered |
|---|---|
| Token/trace observability (Langfuse, Arize, W&B) | What did the model call, spend, and produce? |
| Documentation linters | Is documentation structurally or stylistically valid? |
| trigger-tree | Are project docs discoverable, which were discovered, and did declared instruction probes observe the requested behavior? |

The categories complement each other. trigger-tree does not evaluate answer quality or claim that a read caused an outcome.

## Learn more

[Documentation router](docs/README.md) · [Instruction adherence](docs/instruction-adherence.md) · [Dashboard](docs/dashboard.md) · [Heat model](docs/heat-model.md) · [Configuration](docs/configuration.md) · [Privacy](docs/privacy.md) · [Glossary](docs/glossary.md) · [FAQ](docs/faq.md) · [Website](https://hedde.github.io/trigger_tree/) · [Changelog](CHANGELOG.md)

MIT © Hedde van der Heide
