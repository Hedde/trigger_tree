# 🌳 Trigger Tree

[![CI](https://github.com/Hedde/trigger_tree/actions/workflows/ci.yml/badge.svg)](https://github.com/Hedde/trigger_tree/actions/workflows/ci.yml)
[![coverage](https://img.shields.io/endpoint?url=https%3A%2F%2Fraw.githubusercontent.com%2FHedde%2Ftrigger_tree%2Fbadges%2Fcoverage.json)](https://github.com/Hedde/trigger_tree/actions/workflows/ci.yml)
[![python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![Claude Code plugin](https://img.shields.io/badge/Claude%20Code-plugin-8A2BE2.svg)](https://code.claude.com/docs)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![PRs welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

Claude Code plugin: documentation-discovery telemetry for docs-as-code projects.

Your CLAUDE.md routes tasks through a docs tree — but which paths does the model
*actually* take? Trigger Tree logs every read of a documentation file and every skill
invocation via hooks (shell-side, zero model tokens) to
`$PROJECT/.trigger-tree/history.jsonl`, and turns that history into insights: hot
files, untouched paths, hunting signals, task clusters, and concrete router
improvements. One command:

| Command | Does |
|---------|------|
| `/tt status` | Snapshot: reads, hot files, untouched paths |
| `/tt watch [demo\|replay]` | Live ASCII pulse dashboard (tmux split or new terminal window) |
| `/tt insights` | Analysis report (untouched/dead paths, hunting, trend, clusters) + HTML |
| `/tt note <text>` | Annotate the timeline (e.g. "sharpened UX router") — visible in the trend |
| `/tt setup` | Wire Trigger Tree into a project: gitignore, statusline, optional config |
| `/tt help` | Command overview |

Design principle: discovery stays model-driven (your CLAUDE.md remains the router);
Trigger Tree **measures** it deterministically and helps you sharpen the router with
data instead of gut feeling. Files with zero reads are *untouched* — they are only
called *dead-path candidates* once the measurement is mature (enough reads, sessions,
and days observed). Use `/tt note` when you change the router, then watch the hunting
ratio in the trend: if it falls, the change worked.

Requirements: `python3` only. Works on macOS and Linux (`/tt watch` opens a tmux
split, macOS Terminal, or gnome-terminal/konsole/xterm — whichever is available).

## Install

```
/plugin marketplace add Hedde/trigger_tree
/plugin install tt@trigger-tree
```

Then wire it into your project with `/tt setup` (idempotent: gitignore entries,
statusline registration, and with `/tt setup config` a project-specific
`.trigger-tree/config.sh` override).

Local development from a checkout:

```bash
claude --plugin-dir /path/to/trigger_tree
```

## Configuration (`.trigger-tree/config.sh`, optional)

Overrides the plugin defaults per project:

| Variable | Default | Meaning |
|----------|---------|---------|
| `TT_WATCH_REGEX` | docs/agents/skills/agent-briefs + CLAUDE/AGENTS.md | which reads count as documentation |
| `TT_SCAN_REGEX` | doc folders | which Glob/Grep targets count as hunting |
| `TT_ALWAYS_LOADED_REGEX` | CLAUDE/AGENTS.md, .claude/rules\|skills | auto-loaded files, excluded from untouched analysis |
| `TT_LOG_PROMPTS` | `truncate` | `truncate` (200 chars) · `hash` (sha1 only) · `off` (marker only) |
| `TT_ROTATE_BYTES` | 5 MB | rotate history.jsonl to a timestamped archive beyond this size |

Prompt privacy: fingerprints and clusters work in all three `TT_LOG_PROMPTS` modes —
teams that don't want prompt text on disk use `hash` or `off`.

## Team auto-install

In your project's `.claude/settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "trigger-tree": { "source": { "source": "github", "repo": "Hedde/trigger_tree" } }
  },
  "enabledPlugins": { "tt@trigger-tree": true }
}
```

## What it measures — and what it can't

PostToolUse hooks see real Read/Glob/Grep/Skill tool calls, including those made by
subagents (attributed via `agent_type`). Auto-loaded context (CLAUDE.md,
`.claude/rules`) is invisible to this telemetry and is excluded from untouched-path
analysis as `always_loaded`. Skill invocations *are* measured: an invoked skill's
SKILL.md counts as touched.

## Development

Use a virtual environment (never your system python):

```bash
python3 -m venv .venv && .venv/bin/pip install pytest coverage
.venv/bin/python -m coverage run -m pytest tests -q
.venv/bin/python -m coverage report         # CI gates at 80% minimum
claude plugin validate .
python3 scripts/tt-watch.py --demo          # dashboard with synthetic events
```

CI runs unit + smoke tests with the coverage gate, shellcheck, and plugin validation
on every push. See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.
