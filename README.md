# 🌳 Trigger Tree

[![CI](https://github.com/Hedde/trigger_tree/actions/workflows/ci.yml/badge.svg)](https://github.com/Hedde/trigger_tree/actions/workflows/ci.yml)
[![coverage](https://img.shields.io/endpoint?url=https%3A%2F%2Fraw.githubusercontent.com%2FHedde%2Ftrigger_tree%2Fbadges%2Fcoverage.json)](https://github.com/Hedde/trigger_tree/actions/workflows/ci.yml)
[![python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![platforms](https://img.shields.io/badge/platforms-macOS%20·%20Linux%20·%20Windows-lightgrey.svg)](#platform-support)
[![Claude Code plugin](https://img.shields.io/badge/Claude%20Code-plugin-8A2BE2.svg)](https://code.claude.com/docs)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![PRs welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

> Your CLAUDE.md routes every task through a docs tree — but which paths does the
> model **actually** take? Trigger Tree measures it. **100% local. Zero model tokens.
> No cloud, no analytics vendors.**

✓ heat & cold maps of your documentation &nbsp;·&nbsp; ✓ live pulse dashboard &nbsp;·&nbsp; ✓ evidence-backed router fixes

**[Website](https://hedde.github.io/trigger_tree/)** · [Privacy policy](PRIVACY.md) · [Changelog](CHANGELOG.md)

## Table of contents

- [Quick start](#quick-start) · [Commands](#commands) · [How it works](#how-it-works)
- [The improvement loop](#the-improvement-loop) · [The dashboard](#the-dashboard)
- [Configuration](#configuration) · [Privacy & data](#privacy--data)
- [Platform support](#platform-support) · [FAQ](#faq) · [Development](#development)

## Quick start

```
/plugin marketplace add Hedde/trigger_tree
/plugin install trigger-tree@trigger-tree
/tt setup          # wires gitignore + statusline into your project (idempotent)
```

Work normally for a few sessions — the hooks log silently — then:

```
/tt status         # snapshot: reads, hot files, untouched paths
/tt insights       # full heat/cold map report + HTML
```

## Commands

One plugin, one command, seven subcommands:

| Command | Does |
|---------|------|
| **`/tt status`** | Snapshot of the measurement period: reads, hot files, untouched paths |
| **`/tt watch`** | Live ASCII pulse dashboard (tmux split or a new terminal window) |
| **`/tt watch demo`** | Dashboard with synthetic events — see it without waiting |
| **`/tt insights`** | Heat/cold map analysis: untouched paths, hunting, trend, task clusters + HTML report |
| **`/tt suggestions`** | Max 5 prioritized, evidence-backed router fixes — applied only after you confirm |
| **`/tt note <text>`** | Annotate the timeline ("sharpened UX router") — visible in the trend |
| **`/tt setup`** | Wire Trigger Tree into a project: gitignore, statusline, optional config override |

## How it works

Trigger Tree registers three lightweight hooks — full transparency:

| Hook | Event | Records |
|------|-------|---------|
| SessionStart | new session | session marker |
| UserPromptSubmit | your prompt | task marker (text configurable: truncate/hash/off) |
| PostToolUse | `Read\|Glob\|Grep` and `Skill` | doc path + tool + agent, or skill name |

1. **Hooks log shell-side** to `$PROJECT/.trigger-tree/history.jsonl` — zero model
   tokens, a few milliseconds per tool call, and a logging failure can never break
   your session (loggers always exit 0).
2. **The aggregator is deterministic** — all counting happens in
   `tt-stats.py`; the model only interprets, never computes.
3. **Discovery stays model-driven** — your CLAUDE.md remains the router. Trigger
   Tree *measures* it; it never injects context or overrides routing.

Subagent reads are attributed (`Explore`, `Plan`, …). Auto-loaded context
(CLAUDE.md, `.claude/rules`) is invisible to Read-telemetry by design and excluded
from cold-path analysis; invoked skills *are* measured.

## The improvement loop

Files with zero reads are **untouched** — never called "dead" until the measurement
is mature (enough reads, sessions, and days). Then the loop closes:

1. `/tt insights` shows the **folder heat & cold map** and flags **router gaps**:
   untouched files that no other doc even links to.
2. `/tt suggestions` turns that into concrete edits ("add X to docs/README.md under
   Y — untouched and unreferenced, 0 reads in 3 weeks").
3. You apply, then `/tt note "sharpened UX router"`.
4. The **trend** (hunting ratio per week) shows whether the change actually worked —
   measured, not guessed.

## The dashboard

`/tt watch` opens a live view in a second terminal. Every read flashes white and
ripples up through its parent folders, then fades back to its heat color:

```
 ⠹ TRIGGER TREE  myproject · live doc-discovery

 docs/design/
   ├─ principles.md        ▆  12
   ├─ ui-patterns.md       █  17
   └─ accessibility.md     ·   0
 docs/database/  ·2 untouched
   └─ migrations.md        ▃   4

 33 reads · 2 scans (hunting) · 1 skill uses · 3 sessions
   ● docs/design/ui-patterns.md · 2s ago
   🔍 docs/database [Explore] · 31s ago
```

`--demo` for instant synthetic events, `--replay` to re-run your real history,
`q` or Ctrl+C to quit.

## Configuration

Optional per-project override: `.trigger-tree/config.sh` (create it with
`/tt setup config`):

| Variable | Default | Meaning |
|----------|---------|---------|
| `TT_WATCH_REGEX` | docs/agents/skills/agent-briefs + CLAUDE/AGENTS.md | which reads count as documentation |
| `TT_SCAN_REGEX` | doc folders | which Glob/Grep targets count as hunting |
| `TT_ALWAYS_LOADED_REGEX` | CLAUDE/AGENTS.md, .claude/rules\|skills | auto-loaded files, excluded from cold analysis |
| `TT_LOG_PROMPTS` | `truncate` | `truncate` (200 chars) · `hash` (sha1 only) · `off` (marker only) |
| `TT_ROTATE_BYTES` | 5 MB | rotate history.jsonl to a timestamped archive beyond this size |

Team auto-install — in your project's `.claude/settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "trigger-tree": { "source": { "source": "github", "repo": "Hedde/trigger_tree" } }
  },
  "enabledPlugins": { "trigger-tree@trigger-tree": true }
}
```

## Privacy & data

- ✅ **No network calls of any kind** — python3 standard library only; audit every line.
- ✅ **Nothing leaves your machine** — data lives in `$PROJECT/.trigger-tree/` (gitignored).
- ✅ **Paths and metadata only** — file *contents* are never read or stored.
- ✅ **Prompt text is optional** — `TT_LOG_PROMPTS=hash` or `off` for teams.
- ✅ **You own deletion** — remove `.trigger-tree/` and all history is gone.

Full policy: [PRIVACY.md](PRIVACY.md) · Security reports: [SECURITY.md](SECURITY.md)

## Platform support

| Platform | Telemetry & analysis | `/tt watch` window |
|----------|---------------------|--------------------|
| macOS | ✅ | iTerm2 split (same window), tmux split, or Terminal.app |
| Linux | ✅ | tmux split, gnome-terminal, konsole, xterm |
| Windows | ✅ (Git Bash) | Windows Terminal (`wt.exe`) or `start` |

CI runs the full test suite on all three platforms. Requirements: `python3` (or
`python`) on PATH — nothing else.

## FAQ

**Where is my data?** `$PROJECT/.trigger-tree/history.jsonl`, per project, on your
machine, gitignored.

**Does this slow Claude down?** No tokens are ever spent; the hook adds a few
milliseconds of shell time per Read/Glob/Grep call.

**Why does the statusline say "0 docs consulted" at session start?** CLAUDE.md is
injected into the system prompt, not read via tools — the router is loaded, but
*discovery* hasn't happened yet. That's also why always-loaded files are excluded
from cold-path analysis.

**A file shows as untouched but I know it matters.** Untouched is a signal, not a
verdict — check `/tt insights`: if it's a *router gap* (no doc links to it), the fix
is a link, not deletion.

**Can I turn prompt logging off?** Yes: `TT_LOG_PROMPTS='off'` in
`.trigger-tree/config.sh`. Fingerprints and clusters keep working.

## Development

Always use a virtual environment (never your system python):

```bash
python3 -m venv .venv && .venv/bin/pip install pytest coverage
.venv/bin/python -m coverage run -m pytest tests -q
.venv/bin/python -m coverage report         # CI gates at 80%; the suite sits at 100%
claude plugin validate .
python3 scripts/tt-watch.py --demo
```

CI: pytest + coverage gate on ubuntu/macos/windows, shellcheck, plugin validation,
and a live coverage badge. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE) — © Hedde van der Heide
