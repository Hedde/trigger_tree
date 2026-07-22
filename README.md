# 🌳 trigger-tree

> **See which docs your AI actually discovers.**

<p align="center">
  <img src="assets/trigger-tree-logo.png" alt="trigger-tree documentation discovery logo" width="180">
</p>

[![CI](https://github.com/Hedde/trigger_tree/actions/workflows/ci.yml/badge.svg)](https://github.com/Hedde/trigger_tree/actions/workflows/ci.yml)
[![coverage](https://img.shields.io/endpoint?url=https%3A%2F%2Fraw.githubusercontent.com%2FHedde%2Ftrigger_tree%2Fbadges%2Fcoverage.json)](https://github.com/Hedde/trigger_tree/actions/workflows/ci.yml)
[![release](https://img.shields.io/github/v/release/Hedde/trigger_tree?label=release)](https://github.com/Hedde/trigger_tree/releases/latest)
[![python](https://img.shields.io/badge/python-3.10–3.13-blue.svg)](https://www.python.org/)
[![platforms](https://img.shields.io/badge/platforms-macOS%20·%20Linux%20·%20Windows-lightgrey.svg)](#platform-support)
[![Claude Code plugin](https://img.shields.io/badge/Claude%20Code-plugin-8A2BE2.svg)](https://code.claude.com/docs)
[![Codex plugin](https://img.shields.io/badge/OpenAI%20Codex-plugin-111827.svg)](https://learn.chatgpt.com/docs/build-plugins)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

AI coding assistants read your project documentation to decide how to work.
trigger-tree shows which docs they discover and use — and which ones they never
find. 100% local. Zero model tokens. No cloud, no analytics vendors.

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
bloated CLAUDE.md causes instructions to be ignored — so high-performing teams review
context ruthlessly. But nothing tells them whether those changes were *right*. Agent
observability platforms (Langfuse, Arize, W&B Weave) measure tokens and traces;
none measure which project docs were read per task. And just as
[Fallow](https://github.com/fallow-rs/fallow) made unused-code review evidence-based;
trigger-tree gives you evidence to review, protect, reroute, or rescue docs nobody
dared judge.

| You are | Your question | trigger-tree answers with |
|---------|---------------|---------------------------|
| Senior developer | "Why maintain docs nobody reads?" | Read counts and router gaps per file |
| Tech lead | "Did search activity change after our router edit?" | Correlational trend before/after each `/tt note` |
| Product owner | "We track token cost — where's doc utility?" | One A–F documentation health grade |

## Quick start

### Claude Code

Use this path for `/tt` slash commands, Claude hooks, and the optional Claude
statusline:

```
/plugin marketplace add Hedde/trigger_tree
/plugin install trigger-tree@trigger-tree
/tt setup          # wires the project; local 200-character prompt previews by default
/tt doctor         # proves this repo is wired and receiving telemetry
```

Work normally for a few sessions — the hooks log silently — then:

```
/tt status         # snapshot: current heat, lifetime reads, untouched paths
/tt insights       # full heat/cold map report + HTML
```

### Codex

Use this path for Codex lifecycle hooks and natural-language trigger-tree workflows:

```bash
codex plugin marketplace add Hedde/trigger_tree
codex plugin add trigger-tree@trigger-tree
```

Start a new Codex thread, review and trust the bundled hooks with `/hooks`, then ask
“Show trigger-tree status” or “Open the trigger-tree live dashboard.” Telemetry is
collected automatically from official Codex lifecycle hooks; no wrapper is required.

| | Claude Code | OpenAI Codex |
|---|---|---|
| Install | `/plugin marketplace add` | `codex plugin marketplace add` |
| Invoke | `/tt status`, `/tt watch`, etc. | Ask for the desired trigger-tree workflow |
| Hooks | Claude plugin hooks | Codex lifecycle hooks; trust via `/hooks` |
| Statusline | Optional trigger-tree counter | Codex’s built-in `/statusline` is separate |
| Visible after GitHub install | Claude marketplace/plugin list | Configured marketplace and Installed plugins |

> **GitHub install versus OpenAI Curated:** the commands above install trigger-tree
> directly; they do not add it to OpenAI’s public directory. An OpenAI Curated listing
> requires a separate skills-only submission through the
> [OpenAI plugin portal](https://platform.openai.com/plugins), followed by review,
> approval, and an explicit publish step.

## Claude Code commands and Codex workflows

Claude Code exposes one command with ten subcommands. In Codex, ask for the matching
outcome in natural language; the bundled `trigger-tree` skill runs the same local core.
Claude does not invoke `/tt` automatically: its script-running and artifact-publishing
subcommands require an explicit user slash command.

| Command | Does |
|---------|------|
| **`/tt status`** | Snapshot: current heat, lifetime reads, untouched paths |
| **`/tt watch`** | Live ASCII pulse dashboard (tmux split or a new terminal window) |
| **`/tt watch demo`** | Dashboard with synthetic events — see it without waiting |
| **`/tt insights`** | Heat/cold map analysis: router reachability, search concentration, trend, task clusters + HTML report |
| **`/tt suggestions`** | Concise scope + max 5 evidence-backed fixes; full stats stay off stdout |
| **`/tt note <text>`** | Annotate the timeline ("sharpened UX router") — visible in the trend |
| **`/tt doctor`** | Verify hook files and liveness, watch coverage, privacy, statusline, and telemetry |
| **`/tt setup [truncate\|hash\|off]`** | Wire the project and choose recognizable local previews or privacy-first markers |
| **`/tt uninstall`** | Remove trigger-tree statusline wiring without deleting telemetry |

Tips are intentionally client-specific. Claude advice follows Anthropic's guidance to
[audit auto memory, keep CLAUDE.md concise, and remove conflicting instructions](https://code.claude.com/docs/en/memory).
Codex advice follows OpenAI's guidance to
[maintain AGENTS.md and a reproducible development environment](https://openai.com/business/guides-and-resources/how-openai-uses-codex/).

## How it works

trigger-tree registers three lightweight hooks — full transparency:

| Hook | Event | Records |
|------|-------|---------|
| SessionStart | new session | session marker |
| UserPromptSubmit | your prompt | first 200 characters after setup; choose `hash` or `off` for stronger privacy |
| SessionStart + PostToolUse | `Read\|Glob\|Grep`, `Skill`, and Bash | doc reads, native searches, skill names, explicit `rg`/`grep`/`find` targets, and expanded Bash reader paths |

1. **Hooks log shell-side** to `$PROJECT/.trigger-tree/history.jsonl` — zero model
   tokens, a few milliseconds per tool call, and a logging failure can never break
   your session (loggers always exit 0).
2. **The aggregator is deterministic** — all counting happens in
   `tt-stats.py`; the model only interprets, never computes.
3. **Discovery stays model-driven** — your CLAUDE.md remains the router. trigger-tree
   *measures* it; it never injects context or overrides routing. Bash searches count
   only when `rg`, `grep`, or `find` explicitly targets an existing documentation
   path; search output is never treated as a read. In Bash sessions, lightweight
   reader wrappers observe expanded file arguments after variables, substitutions,
   loops, and globs resolve. They preserve command behavior and record only matching
   paths—not commands, patterns, output, or contents. Other shells use the conservative
   literal-path fallback.

Search telemetry is deliberately a lower bound. Glob calls count only when they have
an explicit path or a non-empty static directory before the first wildcard (for example,
`docs/**/*.md` counts `docs`, while `**/*.md` does not). Grep calls count an explicit
path, or the same conservative prefix from their optional file `glob`; the Grep content
regex is never interpreted as a path.

All `mcp__*` post-tool events reach the small local adapter so documentation tools with
names such as `get_page`, `fetch`, or `retrieve` are not missed. The adapter records
only explicit file-like parameters and drops HTTP(S) targets or calls with no file
parameter; MCP response content is never collected.

Subagent reads are attributed (`Explore`, `Plan`, …). Auto-loaded context—including
the recursive `CLAUDE.md` `@import` graph—is invisible to Read telemetry by design
and classified as **always loaded**; invoked skills *are* measured.

## The improvement loop

Files with zero reads are **review candidates**, never removal recommendations.
Protected context (always-loaded files, safety paths, critical tags/globs, and docs
with many in-links) is called out as likely-keep. Then the loop closes:

1. `/tt insights` shows the **folder heat & cold map**, global in-links, and direct
   reachability from each folder's existing `README.md`, `_index.md`, `index.md`, or
   `CLAUDE.md`. A link elsewhere no longer masks a missing folder-router entry.
2. `/tt suggestions` emits zero to five edits, never a quota. A link proposal is only
   produced when both files exist and the router does not already mention the target.
3. You apply, then `/tt note "sharpened UX router"`.
4. The **trend** shows whether search activity changed after the note. This is
   correlation, not proof that the router edit caused the change.

## The dashboard

`/tt watch` opens a live view in a second terminal. Every read flashes white and
ripples up through its parent folders, then fades back to its heat color:

```
 ⠹ trigger-tree  myproject · live doc-discovery

 docs/design/  · 1 unread
   ├─ principles.md                       ███·· h 3.2 · 12×
   ├─ ui-patterns.md                      █████ h 6.8 · 17×
   └─ accessibility.md     ·   0
 docs/database/  · 🔍 2 searches · 1 unread
   └─ migrations.md                       ██··· h 1.4 · 4×

 33 reads · 2 searches · 1 skill uses · 3 sessions
   ● docs/design/ui-patterns.md · 2s ago
   🔍 docs/database [Explore] · 31s ago
```

Heat and read count are deliberately different signals. **Reads** are the lifetime
evidence and never decrease. **Heat** is current attention: each timestamped read has
weight `0.5^(age_days / 30)`, so its contribution halves every 30 days (1 today,
0.5 after 30 days, 0.125 after 90 days, and effectively zero after a year). A new
read reheats the file immediately. `/tt insights` shows read windows only when the
measurement period is long enough to distinguish them, plus the last-read date and
lifetime reads. Folder heat is the sum
of its file heat. Cold therefore means **inactive now**, never obsolete or safe to
remove; untouched and protected-context classifications remain separate safeguards.
Historical reads for paths that no longer exist are retained under **Retired paths**,
but excluded from current heat, coverage, and health. The report also separates main
and subagent reads, marks unread folder routers, and folds large review queues while
keeping the complete machine-readable data in `stats.json`.

Folder labels keep two signals separate: `🔍 N searches` proves the folder was
explicitly searched, while `N unread` counts files without a Read event. Insights also
show the search tool mix and whether searches are concentrated in a few sessions or
distributed across many. Concentrated bursts may be intentional bulk work; neither
pattern proves why a search occurred. Searching
a folder never pretends its files were consulted; reading one lowers only `unread`.
The same counters are scoped to the selected prompt when browsing with ←/→.
The live tree refreshes its inventory every five seconds: deleted files and folders
disappear from the current overview while their evidence remains available in
historical prompt browsing and aggregate trends.
Recently active folders temporarily move above quiet folders so live work stays
inside a small viewport. They settle back into alphabetical order after eight
seconds; files within folders and prompt-history views remain alphabetically stable.
The live view shows at most ten folders with proven activity and collapses untouched
folders/files into one quiet summary. `/tt insights` remains the complete cold-path
inventory; nothing is removed from the underlying telemetry.

The live rows use horizontal five-cell heat bars and place their heat/lifetime
column against the available right edge, so wider panes expose more of long filenames
instead of leaving unused space. Sorting is explicit: `f` restores recent-focus,
`h` shows hottest first, `c` shows coldest first (including untouched files), and
`n` toggles A–Z and Z–A. Always-loaded `CLAUDE.md`, `AGENTS.md`, rules, and skills
are labeled `injected` instead of being misrepresented as cold. The current mode is
always printed in the footer. Press `s` to change prompt privacy inside the dashboard;
changes apply to future prompts and are written atomically to the gitignored project config.
The live dashboard also rotates one quiet maintenance tip every 30 seconds. Tips are
repository-aware and client-specific: Claude sees memory/rules guidance, while Codex sees
AGENTS.md and verification guidance. The telemetry statusline itself remains stable.
The controls occupy their own persistent legend row (with a compact form for narrow
panes), separate from prompt navigation and the live heartbeat, so the keys remain
discoverable instead of disappearing at the right edge.

**Browse per prompt**: press ← to move to older prompts and → to move to newer
ones — the tree filters to exactly what was aggregated for that input (its reads,
scans and skill uses, with its prompt label in the header). The timeline never wraps or
changes mode at its ends; `a` returns to the live overview.

`/tt setup` defaults to `TT_LOG_PROMPTS='truncate'`, so history shows a recognizable
preview of at most 200 characters. The data remains local and gitignored, but it is
still prompt text on disk. Choose `/tt setup hash` for stable fingerprints without
text, or `/tt setup off` for marker-only history. Only future prompts are affected;
previously hashed prompt text cannot and should not be reconstructed.

`--demo` for instant synthetic events, `--replay` to re-run your real history,
`q` or Ctrl+C to quit. The watcher uses a full-screen terminal buffer with wrapping
disabled, so refreshes do not accumulate as scrollback; your normal terminal state
is restored when it exits.

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

Per-project settings live in `.trigger-tree/config.sh` (created by `/tt setup`):

| Variable | Default | Meaning |
|----------|---------|---------|
| `TT_WATCH_REGEX` | docs/agents/skills/agent-briefs + CLAUDE/AGENTS.md | which reads count as documentation |
| `TT_SCAN_REGEX` | doc folders | which Glob/Grep and explicit Bash-search targets count as hunting |
| `TT_ALWAYS_LOADED_REGEX` | CLAUDE/AGENTS.md, .claude/skills | auto-loaded files, augmented by recursive `@imports` and excluded from review candidates |
| `TT_CRITICAL_GLOB` | empty | comma-separated globs protected as rare-but-critical review items |
| `TT_LOG_PROMPTS` | `truncate` after setup; `hash` without config | `truncate` (200 local chars) · `hash` (sha1 only) · `off` (marker only) |
| `TT_ROTATE_BYTES` | 5 MB | rotate history.jsonl to a timestamped archive beyond this size |
| `TT_EXPERIMENTAL_OUTCOMES` | `off` | `on` enables a local, correlational committed-vs-abandoned session view |

The default watch scope is a starting point, not a claim about every repository layout.
`/tt setup` always reports how many local Markdown files it covers and proposes an
observed-location regex when coverage is poor; it does not apply that regex unless
`tt-setup.py --apply-watch-suggestion` is explicitly requested. `/tt doctor` fails on
zero matches and warns when the watched share is very low, naming the exact
`TT_WATCH_REGEX` setting in `.trigger-tree/config.sh` to adjust.

The experimental outcome view records whether the repository HEAD changed during a
session and the latest locally observed test-command result. It compares documents
read in committed versus abandoned sessions. This is correlation only: it does not
claim that reading a document caused an outcome.

### Uninstall

Run `/tt uninstall` to remove the trigger-tree `statusLine` registration and the copied
`.claude/tt-statusline.py`. A foreign statusline is never changed. The command leaves
`.trigger-tree/` and its `.gitignore` entries in place so telemetry is never destroyed
implicitly; delete those manually only when you intend to erase the local history.

Team auto-install — in your project's `.claude/settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "trigger-tree": { "source": { "source": "github", "repo": "Hedde/trigger_tree" } }
  },
  "enabledPlugins": { "trigger-tree@trigger-tree": true }
}
```

### Codex adapter and external tools

Codex support is native. Its adapter normalizes official lifecycle events, unified
terminal `cmd` payloads, native reads, and filesystem MCP reads into the same history
schema used by Claude Code. Starting Codex from a repository subdirectory still writes
to the repository-root dataset.

Git hooks, editors, and other tools can feed that same telemetry through a stable entry
point:

```bash
python3 <plugin>/scripts/tt-log.py ingest '{"t":"read","path":"docs/design/index.md"}'
```

Missing `ts`/`session` are stamped automatically; invalid events are dropped silently.

## Privacy & data

- ✅ **No network calls of any kind** — python3 standard library only; audit every line.
- ✅ **Nothing leaves your machine** — data lives in `$PROJECT/.trigger-tree/` (gitignored).
- ✅ **Paths and metadata only** — file *contents* are never read or stored.
- ✅ **Prompt privacy is explicit** — setup explains its local preview default; `hash` and `off` remain one-command alternatives.
- ✅ **You own deletion** — remove `.trigger-tree/` and all history is gone.

Full policy: [PRIVACY.md](PRIVACY.md) · Security reports: [SECURITY.md](SECURITY.md)

## Platform support

| Platform | Telemetry & analysis | `/tt watch` window |
|----------|---------------------|--------------------|
| macOS | ✅ | iTerm2 split (same window), tmux split, or Terminal.app |
| Linux | ✅ | tmux split, gnome-terminal, konsole, xterm |
| Windows | ✅ Python runtime and CI | Windows Terminal (`wt.exe`) or `start` |

CI runs the full Python test suite on all three platforms and validates the Claude
hook manifest. Native Windows hook launch is not exercised end-to-end in CI; Claude's
[documented shell-free exec form](https://code.claude.com/docs/en/hooks#command-hook-fields)
is used so plugin paths are substituted without shell quoting. The Claude hook path
requires `python3` on `PATH`; no other runtime dependency is needed.

## Limitations

Honesty over marketing — know what the measurement can and cannot see:

- **Injected context is invisible.** Root/nested CLAUDE.md, `.claude/rules` and
  `@imports` enter the context without a Read call; trigger-tree lists them as
  *always loaded* rather than guessing. Only tool-driven reads are measurable.
- **Read ≠ understood.** A read count proves discovery, not that the content was
  good or followed. Pair the telemetry with your own judgment.
- **Signals, not verdicts.** Untouched files are *review candidates*, never removal
  recommendations. Always-loaded, widely referenced, safety-path, configured-critical,
  and critical-tagged files are protected; low reads can mean rare-but-critical.
- **Tool hooks have surface boundaries.** Claude Code and Codex are supported natively.
  Hosted tools that bypass local lifecycle hooks remain invisible; other local tools can
  participate through `ingest` (see Codex adapter and external tools).

## FAQ

**Where is my data?** `$PROJECT/.trigger-tree/history.jsonl`, per project, on your
machine, gitignored.

**Does this slow the agent down?** No tokens are ever spent; the hook adds a few
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

**How do I know this repository is wired correctly?** Run `/tt doctor`. It distinguishes
intact packaged hook files from evidence that hooks actually fired, checks watch-regex
coverage, local-data gitignore, statusline registration, and whether this exact
repository has received valid telemetry. `/tt watch` always binds its split
to the repository that invoked it and tails new hook events in real time.

**Why is Claude telemetry empty on Windows?** Claude's documented exec-form hooks
cannot select an executable by operating system: the `if` field filters tool calls,
not platforms. Ensure `python3` resolves on `PATH` by enabling the Windows `python3`
app alias or creating an equivalent command that launches your Python 3 installation.

**Can I change prompt logging?** Yes: `/tt setup truncate` stores recognizable
200-character previews locally, `/tt setup hash` stores only a short SHA-1 fingerprint,
and `/tt setup off` stores marker-only events. Existing history is not rewritten.

## Development

Always use a virtual environment (never your system python):

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-test.txt -r requirements-dev.txt
.venv/bin/black --check scripts tests .github/scripts
.venv/bin/ruff check scripts tests .github/scripts
.venv/bin/python -m coverage run -m pytest tests -q
.venv/bin/python -m coverage report --fail-under=100
shellcheck scripts/tt-open.sh scripts/tt-shell-capture.sh
claude plugin validate .
python3 scripts/tt-watch.py --demo
```

CI: Black + Ruff, pytest with a 100% coverage gate on Ubuntu/macOS/Windows, Python
3.10–3.13 compatibility, shellcheck, actionlint + zizmor workflow auditing, plugin
validation, and an isolated marketplace-install smoke test. Release tags must agree
with the manifest and changelog. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE) — © Hedde van der Heide
