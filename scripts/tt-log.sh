#!/bin/bash
# Trigger Tree logger — invoked by the plugin hooks (SessionStart, UserPromptSubmit, PostToolUse).
# Appends one JSON line per event to $PROJECT/.trigger-tree/history.jsonl. Zero model tokens.
# Events: session (session start), prompt (user prompt marker), read/scan (Read/Glob/Grep).
set -uo pipefail

EVENT="${1:?usage: tt-log.sh session|prompt|read}"
ROOT="${CLAUDE_PROJECT_DIR:-$(pwd)}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Project override wins over the plugin default.
if [ -f "$ROOT/.trigger-tree/config.sh" ]; then
  source "$ROOT/.trigger-tree/config.sh"
else
  source "$SCRIPT_DIR/tt-config.sh"
fi

HIST_DIR="$ROOT/.trigger-tree"
HIST="$HIST_DIR/history.jsonl"
mkdir -p "$HIST_DIR"

INPUT=$(cat)
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
SESSION=$(jq -r '.session_id // "?"' <<<"$INPUT")

case "$EVENT" in
  session)
    jq -cn --arg ts "$TS" --arg s "$SESSION" \
      '{t:"session", ts:$ts, session:$s}' >> "$HIST"
    ;;
  prompt)
    PROMPT=$(jq -r '.prompt // ""' <<<"$INPUT" | tr '\n' ' ' | cut -c1-200)
    jq -cn --arg ts "$TS" --arg s "$SESSION" --arg p "$PROMPT" \
      '{t:"prompt", ts:$ts, session:$s, prompt:$p}' >> "$HIST"
    ;;
  read)
    TOOL=$(jq -r '.tool_name // "?"' <<<"$INPUT")
    AGENT=$(jq -r '.agent_type // "main"' <<<"$INPUT")
    if [ "$TOOL" = "Read" ]; then
      TARGET=$(jq -r '.tool_input.file_path // empty' <<<"$INPUT")
      TYPE="read"
      REGEX="$TT_WATCH_REGEX"
    else
      TARGET=$(jq -r '.tool_input.path // empty' <<<"$INPUT")
      TYPE="scan"
      REGEX="$TT_SCAN_REGEX"
    fi
    [ -z "$TARGET" ] && exit 0
    REL="${TARGET#"$ROOT"/}"
    grep -qE "$REGEX" <<<"$REL" || exit 0
    jq -cn --arg ts "$TS" --arg s "$SESSION" --arg type "$TYPE" --arg tool "$TOOL" --arg path "$REL" --arg agent "$AGENT" \
      '{t:$type, ts:$ts, session:$s, tool:$tool, path:$path, agent:$agent}' >> "$HIST"
    ;;
esac
exit 0
