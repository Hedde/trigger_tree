# 🌳 Trigger Tree

Claude Code plugin: documentation-discovery telemetry for docs-as-code projects.

Your CLAUDE.md routes tasks through a docs tree — but which paths does the model
*actually* take? Trigger Tree logs every read of a documentation file via hooks
(shell-side, zero model tokens) to `$PROJECT/.trigger-tree/history.jsonl`, and turns
that history into insights: hot files, untouched paths, hunting signals, and concrete
router improvements. One command:

| Command | Does |
|---------|------|
| `/tt status` | Snapshot: reads, hot files, untouched paths |
| `/tt watch [demo\|replay]` | Live ASCII pulse dashboard in a new terminal window |
| `/tt insights` | Analysis report (untouched/dead paths, hunting, router proposals) + HTML |
| `/tt help` | Command overview |

Design principle: discovery stays model-driven (your CLAUDE.md remains the router);
Trigger Tree **measures** it deterministically and helps you sharpen the router with
data instead of gut feeling. Files with zero reads are *untouched* — they are only
called *dead-path candidates* once the measurement is mature (enough reads, sessions,
and days observed).

## Install

```
/plugin marketplace add Hedde/trigger_tree
/plugin install tt@trigger-tree
```

Local development from a checkout:

```bash
claude --plugin-dir /path/to/trigger-tree
```

## Per-project configuration

- **Which paths count as documentation**: override `scripts/tt-config.sh` by placing a
  `.trigger-tree/config.sh` in your project root (same variables).
- **Statusline** (cannot ship via a plugin): register `tt-statusline.sh` in your project
  or user settings under `statusLine` (with `refreshInterval` for the pulse dot):

  ```json
  {
    "statusLine": {
      "type": "command",
      "command": "/path/to/tt-statusline.sh",
      "refreshInterval": 5
    }
  }
  ```

- **Gitignore**:

  ```
  .trigger-tree/*
  !.trigger-tree/config.sh
  ```

- **Team auto-install**: in your project's `.claude/settings.json`:

  ```json
  {
    "extraKnownMarketplaces": {
      "trigger-tree": { "source": { "source": "github", "repo": "Hedde/trigger_tree" } }
    },
    "enabledPlugins": { "tt@trigger-tree": true }
  }
  ```

## What it measures — and what it can't

PostToolUse hooks see real Read/Glob/Grep tool calls only, including those made by
subagents (attributed via `agent_type`). Auto-loaded context (CLAUDE.md,
`.claude/rules`, SKILL.md files loaded via the Skill tool) is invisible to this
telemetry and is therefore excluded from untouched-path analysis as `always_loaded`.

Requirements: `jq`, `python3`. The `/tt watch` window launcher is macOS-only for now
(`osascript`); on other platforms run `python3 scripts/tt-watch.py` in a second
terminal manually.

## Development

```bash
claude plugin validate .
python3 scripts/tt-watch.py --demo          # dashboard with synthetic events
python3 scripts/tt-stats.py | jq .totals    # run the aggregator standalone
```
