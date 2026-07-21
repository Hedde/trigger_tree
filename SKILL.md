---
name: tt
description: See which docs your AI actually discovers with local, zero-token telemetry. Subcommands; /tt status, /tt watch [demo|replay], /tt insights, /tt suggestions, /tt tips, /tt note <text>, /tt doctor, /tt setup, /tt help.
disable-model-invocation: true
allowed-tools: Bash, Read, Write, Artifact
arguments:
  - subcommand
  - option
---

# /tt — trigger-tree

Execute the subcommand in `$1` (option/text in `$2` and beyond; `$ARGUMENTS` holds everything).

**Output discipline — the most important rule:** work silently. No plan up front, no
intermediate status lines, no explanation of what you are about to do or just did.
Execute the steps and show only the end result in the format specified per subcommand
below. Report an error in exactly one line.

**Terminology — maturity model:** a file with zero reads is **untouched**, never "dead".
Only when the stats JSON reports `maturity: "mature"` may untouched files be presented
as **dead-path candidates**. During `cold-start` and `warming` the measurement is simply
too young to judge.

Scripts live in `${CLAUDE_SKILL_DIR}/scripts/`. Project data lives in
`${CLAUDE_PROJECT_DIR}/.trigger-tree/`.

## `$1` = "help" or empty

Show exactly this, nothing above or below it:

> **🌳 trigger-tree** — measures which documentation your agents actually use
>
> | Command | Does |
> |---------|------|
> | `/tt status` | Snapshot: current heat, lifetime reads, untouched paths |
> | `/tt watch` | Live dashboard; heat bars, injected context, privacy settings, and focus/hot/cold/A–Z/Z–A sorting |
> | `/tt watch demo` | Dashboard with synthetic events (writes nothing) |
> | `/tt watch replay` | Dashboard replaying the real history, accelerated |
> | `/tt insights` | Analysis report: heat/cold map, untouched paths, hunting, trend + HTML |
> | `/tt suggestions` | Max 5 prioritized, concrete router fixes — apply after confirmation |
> | `/tt tips` | Concise Claude-specific instruction and memory maintenance tips |
> | `/tt note <text>` | Annotate the timeline (e.g. "sharpened UX router") — shows up in the trend |
> | `/tt doctor` | Verify hooks, privacy, statusline, and telemetry with actionable fixes |
> | `/tt setup [truncate\|hash\|off]` | Wire the project; choose recognizable previews or privacy-first prompt markers |
> | `/tt help` | This overview |
>
> Telemetry runs automatically via hooks; the statusline shows the live session counter.

## `$1` = "status"

1. Silently run `python3 "${CLAUDE_SKILL_DIR}/scripts/tt-stats.py"` and read the JSON.
2. Show only this block:

> **🌳 trigger-tree status** _(period: <observed_from> → <observed_to>, <sessions> sessions)_
> <reads> reads · <scans> scans · <skill_uses> skill uses · <files touched>/<inventory_files> files touched
> **Health:** <health.grade> (<health.score>/100) — append "(provisional)" unless maturity is `mature`
>
> **Current heat:** sort `files` by `heat` descending and show the top 5 as
> `path (h<heat>, <reads>× lifetime)`, comma-separated.
> **Untouched:** <count of untouched> — followed by the maturity suffix:
> - `cold-start`: "(measurement just started — nothing can be called dead yet)"
> - `warming`: "(early signal — more sessions needed before judging)"
> - `mature`: "(dead-path candidates — see /tt insights)"

## `$1` = "watch"

1. Silently run `"${CLAUDE_SKILL_DIR}/scripts/tt-open.sh" $2` (`$2` empty, `demo` or `replay`).
2. Answer with exactly the confirmation line the script prints (it reports tmux split /
   new window / used terminal). If the script fails, report the cause in one line (on
   first use macOS may ask for Automation permission; mention that if the error points to it).

## `$1` = "insights"

1. Silently run `python3 "${CLAUDE_SKILL_DIR}/scripts/tt-stats.py"` and read the JSON.
2. If `maturity` is `cold-start`: answer in one line —
   `🌳 Not enough data yet (<reads> reads, <sessions> sessions) — check back after a few working sessions.` Stop.
3. Silently run `python3 "${CLAUDE_SKILL_DIR}/scripts/tt-report.py"` — it writes
   `.trigger-tree/report.html` and prints the path.
4. Publish that file with the Artifact tool (favicon `🌳`, description "trigger-tree
   documentation telemetry report"). No Artifact tool available → use the local path
   as the link.
5. Show only the final report, compact (guideline ≤ 15 lines):

> **🌳 trigger-tree insights** _(period, #sessions, maturity)_
>
> **Health** — grade + score with its three drivers, one line ("(provisional)" unless mature).
> **Key figures** — reads, scans (hunting ratio), skill uses, files touched / inventory.
> **Folder heat/cold map** — from `folders`: name the hottest folder by current
> decayed `heat` (also state 30-day and lifetime reads) and the least-covered folder,
> one line each. Cold means inactive now, not obsolete.
> **Untouched paths** — when `mature`: one line per path with a category — 🗑 remove/merge,
> 🧭 sharpen router (with a concrete proposal), 📦 intentional archive. Use
> `untouched_detail`: a path with empty `referenced_from` is a **router gap** (no doc
> links to it) — that's nearly always 🧭; `template: true` entries are automatically 📦.
> When `warming`: present as untouched with the note that judgment needs more data;
> no categories.
> **Trend** — only when `trend` has 2+ periods: is the hunting ratio falling or rising,
> and does that correlate with any `notes` (router changes)?
> **Hunting** — only if scans > 20% of reads: which folder, what that suggests.
> **Task clusters** — top 2-3 from `clusters`: "tasks like <example prompt> consistently
> use <paths>" — flag when a cluster misses an obvious doc.
> **Router proposals** — max 3, concrete ("add X to docs/README.md under Y").
>
> 📊 Full report: <artifact link or file path>

Analysis rules (do not repeat them in the output): lifetime read counts never decay;
current `heat` uses the `heat_model` 30-day half-life and is distinct from untouched;
read counts and heat are signals, not verdicts;
files in `always_loaded` are never dead by definition (system-prompt injection); a file
younger than the measurement period is new, not untouched; subagent reads (the `agents`
field) count fully; skill uses make `.claude/skills/**` measurable — an invoked skill's
SKILL.md counts as touched.

## `$1` = "suggestions"

Silently run `python3 "${CLAUDE_SKILL_DIR}/scripts/tt-suggestions.py"` (fall back to
`python` if needed) and show its concise output verbatim. The script keeps full stats
off stdout, explains its evidence scope, prints at most five deterministic router
edits, and changes nothing. Apply only numbers the user explicitly confirms, then
suggest recording the change with `/tt note`.

## `$1` = "tips"

Silently run `python3 "${CLAUDE_SKILL_DIR}/scripts/tt-tips.py" --client claude`
(fall back to `python` if needed) and show its concise output verbatim. These are
maintenance recommendations only; do not edit memory or instruction files automatically.

## `$1` = "note"

1. Take everything after the subcommand as the note text. Silently run:
   `python3 "${CLAUDE_SKILL_DIR}/scripts/tt-log.py" note "<text>"`
   (the CLAUDE_SESSION_ID environment variable is picked up automatically when present).
2. Answer with exactly one line: `🌳 Noted: "<text>" — it will show up in the trend timeline.`
   Empty text → `Usage: /tt note <text>` in one line.

## `$1` = "setup"

1. Silently run `python3 "${CLAUDE_SKILL_DIR}/scripts/tt-setup.py"`. If `$2` is
   `truncate`, `hash`, or `off`, append `--prompt-mode "$2"`. The default creates
   truncated local previews; an existing config is preserved unless a mode is explicit.
2. Show the script's summary lines verbatim (they report created/updated/skipped per
   step), nothing else.

## `$1` = "doctor"

Silently run `python3 "${CLAUDE_SKILL_DIR}/scripts/tt-doctor.py"` (fall back to
`python` if needed). Show its output verbatim. A failed check is a diagnostic result,
not a skill error: still show the complete output.

## Any other `$1`

Answer with exactly one line: `Unknown subcommand '$1' — try /tt help.`
