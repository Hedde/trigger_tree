# 🌳 trigger-tree

[![CI](https://github.com/Hedde/trigger_tree/actions/workflows/ci.yml/badge.svg)](https://github.com/Hedde/trigger_tree/actions/workflows/ci.yml)
[![coverage](https://img.shields.io/endpoint?url=https%3A%2F%2Fraw.githubusercontent.com%2FHedde%2Ftrigger_tree%2Fbadges%2Fcoverage.json)](https://github.com/Hedde/trigger_tree/actions/workflows/ci.yml)
[![python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![platforms](https://img.shields.io/badge/platforms-macOS%20·%20Linux%20·%20Windows-lightgrey.svg)](#platform-support)
[![Claude Code plugin](https://img.shields.io/badge/Claude%20Code-plugin-8A2BE2.svg)](https://code.claude.com/docs)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![PRs welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

> **AI coding assistants read your project documentation to decide how to work.
> trigger-tree shows you which docs they actually use — and which ones they never
> find.** 100% local. Zero model tokens. No cloud, no analytics vendors.

✓ heat & cold maps of your documentation &nbsp;·&nbsp; ✓ live pulse dashboard &nbsp;·&nbsp; ✓ evidence-backed router fixes

**[Website](https://hedde.github.io/trigger_tree/)** · [Privacy policy](PRIVACY.md) · [Changelog](CHANGELOG.md)

## Table of contents

- [Why measure documentation?](#why-measure-documentation) · [Quick start](#quick-start) · [Commands](#commands)
- [How it works](#how-it-works) · [The improvement loop](#the-improvement-loop) · [The dashboard](#the-dashboard)
- [Structuring your docs for discovery](#structuring-your-docs-for-discovery)
- [Configuration](#configuration) · [Privacy & data](#privacy--data)
- [Platform support](#platform-support) · [FAQ](#faq) · [Development](#development)

## Why measure documentation?

In AI-assisted development, documentation is no longer just for humans — it is the
**steering wheel**. Your CLAUDE.md, conventions, and architecture docs tell the
assistant how *your* team builds software: which patterns to copy, which guardrails
to respect, which decisions were already made. When the assistant reads the right
doc, it works your way. When it doesn't, it guesses.

And here is the uncomfortable part: **a rule that is never read protects nothing.**
Teams invest heavily in writing docs, then assume they work — but an unread
guardrail fails silently. You only notice when the AI "ignores" a convention that,
in truth, it simply never found.

trigger-tree closes that loop. It measures which docs are actually consulted per
task, surfaces the ones that never are (and *why* — unrouted? unreferenced? obsolete?),
and proves whether your fixes worked. Documentation stops being a hopeful artifact
and becomes monitored infrastructure — with a health grade to track sprint over sprint.

**This measurement doesn't exist anywhere else.** Anthropic's own
[best-practices guide](https://code.claude.com/docs/en/best-practices) warns that a
bloated CLAUDE.md causes instructions to be ignored — so high-performing teams prune
ruthlessly. But nothing tells them whether the pruning was *right*. Agent
observability platforms (Langfuse, Arize, W&B Weave) measure tokens and traces;
none measure which project docs were read per task. And just as
[Fallow](https://github.com/fallow-rs/fallow) gave teams the confidence to delete
code nobody dared touch, trigger-tree gives you the evidence to prune, reroute, or
rescue docs nobody dared judge.

| You are | Your question | trigger-tree answers with |
|---------|---------------|---------------------------|
| Senior developer | "Why maintain docs nobody reads?" | Read counts and router gaps per file |
| Tech lead | "Was our CLAUDE.md pruning correct?" | Trend: hunting ratio before/after each `/tt note` |
| Product owner | "We track token cost — where's doc utility?" | One A–F documentation health grade |

## Quick start

```
/plugin marketplace add Hedde/trigger_tree
/plugin install trigger-tree@trigger-tree
/tt setup          # wires gitignore + statusline into your project (idempotent)
/tt doctor         # proves this repo is wired and receiving telemetry
```

Work normally for a few sessions — the hooks log silently — then:

```
/tt status         # snapshot: reads, hot files, untouched paths
/tt insights       # full heat/cold map report + HTML
```

## Commands

One plugin, one command, eight subcommands:

| Command | Does |
|---------|------|
| **`/tt status`** | Snapshot of the measurement period: reads, hot files, untouched paths |
| **`/tt watch`** | Live ASCII pulse dashboard (tmux split or a new terminal window) |
| **`/tt watch demo`** | Dashboard with synthetic events — see it without waiting |
| **`/tt insights`** | Heat/cold map analysis: untouched paths, hunting, trend, task clusters + HTML report |
| **`/tt suggestions`** | Concise scope + max 5 evidence-backed fixes; full stats stay off stdout |
| **`/tt note <text>`** | Annotate the timeline ("sharpened UX router") — visible in the trend |
| **`/tt doctor`** | Verify hooks, privacy, statusline, and live telemetry with actionable fixes |
| **`/tt setup`** | Wire trigger-tree into a project: gitignore, statusline, optional config override |

## How it works

trigger-tree registers three lightweight hooks — full transparency:

| Hook | Event | Records |
|------|-------|---------|
| SessionStart | new session | session marker |
| UserPromptSubmit | your prompt | task marker (text configurable: truncate/hash/off) |
| PostToolUse | `Read\|Glob\|Grep`, `Skill`, and Bash | doc reads, native searches, skill names, plus explicit `rg`/`grep`/`find` doc targets |

1. **Hooks log shell-side** to `$PROJECT/.trigger-tree/history.jsonl` — zero model
   tokens, a few milliseconds per tool call, and a logging failure can never break
   your session (loggers always exit 0).
2. **The aggregator is deterministic** — all counting happens in
   `tt-stats.py`; the model only interprets, never computes.
3. **Discovery stays model-driven** — your CLAUDE.md remains the router. trigger-tree *measures* it; it never injects context or overrides routing. Bash searches count only when `rg`, `grep`, or `find` explicitly targets an existing documentation path; search output is never treated as a read.

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
 ⠹ trigger-tree  myproject · live doc-discovery

 docs/design/  · 1 unread
   ├─ principles.md        ▆  12
   ├─ ui-patterns.md       █  17
   └─ accessibility.md     ·   0
 docs/database/  · 🔍 2 searches · 1 unread
   └─ migrations.md        ▃   4

 33 reads · 2 scans (hunting) · 1 skill uses · 3 sessions
   ● docs/design/ui-patterns.md · 2s ago
   🔍 docs/database [Explore] · 31s ago
```

Folder labels keep two signals separate: `🔍 N searches` proves the folder was
explicitly searched, while `N unread` counts files without a Read event. Searching
a folder never pretends its files were consulted; reading one lowers only `unread`.
The same counters are scoped to the selected prompt when browsing with ←/→.

**Browse per prompt**: press ← to move to older prompts and → to move to newer
ones — the tree filters to exactly what was aggregated for that input (its reads,
scans and skill uses, with the prompt text in the header). The timeline never wraps
or changes mode at its ends; `a` returns to the live overview.

`--demo` for instant synthetic events, `--replay` to re-run your real history,
`q` or Ctrl+C to quit.

## Structuring your docs for discovery

How should a docs tree look so an assistant actually finds things? Claude Code has
native mechanisms, and there is one popular community convention — trigger-tree
measures whichever you use. The facts, per the
[official memory docs](https://code.claude.com/docs/en/memory.md):

| Mechanism | Loads | Status |
|-----------|-------|--------|
| Root `CLAUDE.md` — keep it **under 200 lines**, pointers over inlining | at launch | ✅ official |
| Nested `CLAUDE.md` per subdirectory | on demand, when files there are read | ✅ official |
| `.claude/rules/*.md` with `paths:` glob frontmatter | on demand, on matching files | ✅ official |
| `@imports` (`@docs/foo.md`, max 4 hops deep) | at launch — they always cost context | ✅ official |
| Per-folder `index.md`/`README.md` routers + `_template.md` | when the model follows your router instructions | community pattern |

Practical guidance, as encoded in `/tt suggestions`:

1. **Root CLAUDE.md is a router, not a manual.** Short, with a task→docs map
   ("UI work → docs/design/, start at index.md").
2. **Give every folder one entry point** — an `index.md` (or a nested `CLAUDE.md`)
   that says what lives there and when to read what. trigger-tree flags folders
   without one ("no index file") and `/tt suggestions` proposes adding it.
3. **Know the measurement trade-off.** Injected context (root and nested CLAUDE.md,
   rules, imports) is invisible to read-telemetry — trigger-tree honestly lists it
   as *always loaded* instead of guessing. Router files read via tools (`index.md`)
   **are** measurable. If you want provable discovery, route through index files
   and keep injected files thin.
4. **Prefix templates with `_`** (`_template.md`). Claude attaches no special
   meaning to the underscore — but trigger-tree recognizes the convention and files
   them as intentional archive instead of nagging you about "dead" templates.

## Configuration

Optional per-project override: `.trigger-tree/config.sh` (create it with
`/tt setup config`):

| Variable | Default | Meaning |
|----------|---------|---------|
| `TT_WATCH_REGEX` | docs/agents/skills/agent-briefs + CLAUDE/AGENTS.md | which reads count as documentation |
| `TT_SCAN_REGEX` | doc folders | which Glob/Grep and explicit Bash-search targets count as hunting |
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

### External tools (Codex, git hooks, editors)

Other tools don't fire Claude Code hooks, but they can feed the same telemetry
through a stable adapter entry point:

```bash
python3 <plugin>/scripts/tt-log.py ingest '{"t":"read","path":"docs/design/index.md"}'
```

Missing `ts`/`session` are stamped automatically; invalid events are dropped
silently. A Codex wrapper is just a few lines around this call — the plugin side
is ready.

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

## Limitations

Honesty over marketing — know what the measurement can and cannot see:

- **Injected context is invisible.** Root/nested CLAUDE.md, `.claude/rules` and
  `@imports` enter the context without a Read call; trigger-tree lists them as
  *always loaded* rather than guessing. Only tool-driven reads are measurable.
- **Read ≠ understood.** A read count proves discovery, not that the content was
  good or followed. Pair the telemetry with your own judgment.
- **Signals, not verdicts.** Untouched files are only called *dead-path candidates*
  once the measurement is mature; new files, templates, and runbooks are recognized
  and treated accordingly.
- **Claude Code hooks only fire in Claude Code.** Other tools can participate via
  the `ingest` adapter entry point (see External tools) — but only if you wire them up.

## FAQ

**Where is my data?** `$PROJECT/.trigger-tree/history.jsonl`, per project, on your
machine, gitignored.

**Does this slow Claude down?** No tokens are ever spent; the hook adds a few
milliseconds of shell time per relevant tool call.

**Why does the statusline say "0 docs consulted" at session start?** CLAUDE.md is
injected into the system prompt, not read via tools — the router is loaded, but
*discovery* hasn't happened yet. That's also why always-loaded files are excluded
from cold-path analysis.

**A file shows as untouched but I know it matters.** Untouched is a signal, not a
verdict — check `/tt insights`: if it's a *router gap* (no doc links to it), the fix
is a link, not deletion.

**The `/tt watch` split flashes and disappears instantly.** Your session is running
a stale cached plugin version from before v0.3.3. Run `/reload-plugins` in that
session (or start a fresh one). Since v0.3.7 the confirmation line prints the
running version — if it doesn't match the [latest release](https://github.com/Hedde/trigger_tree/releases),
reload. A *real* crash keeps the pane open with the error since v0.3.3.

**How do I know this repository is wired correctly?** Run `/tt doctor`. It checks
the plugin hooks, local-data gitignore, statusline registration, and whether this
exact repository has received valid telemetry. `/tt watch` always binds its split
to the repository that invoked it and tails new hook events in real time.

**Can I turn prompt logging off?** Yes: `TT_LOG_PROMPTS='off'` in
`.trigger-tree/config.sh`. Fingerprints and clusters keep working.

## Development

Always use a virtual environment (never your system python):

```bash
python3 -m venv .venv && .venv/bin/pip install pytest coverage
.venv/bin/python -m coverage run -m pytest tests -q
.venv/bin/python -m coverage report --fail-under=100
claude plugin validate .
python3 scripts/tt-watch.py --demo
```

CI: pytest + a 100% coverage gate on ubuntu/macos/windows, shellcheck, plugin validation,
and a live coverage badge. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE) — © Hedde van der Heide
