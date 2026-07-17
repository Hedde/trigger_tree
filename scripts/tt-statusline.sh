#!/bin/bash
# Trigger Tree statusline — live doc-discovery stats for the current session.
# The dot pulses: ● bright green = read <90s ago, ◐ amber = <10min, ○ dim = older.
# Configured in .claude/settings.json under "statusLine" (refreshInterval re-renders it).
set -uo pipefail

INPUT=$(cat)
ROOT="${CLAUDE_PROJECT_DIR:-$(pwd)}"
HIST="$ROOT/.trigger-tree/history.jsonl"
SESSION=$(jq -r '.session_id // empty' <<<"$INPUT")

if [ -z "$SESSION" ] || [ ! -f "$HIST" ]; then
  echo "🌳 tt: no data"
  exit 0
fi

LINES=$(grep -F "\"session\":\"$SESSION\"" "$HIST" 2>/dev/null || true)
STATS=$(echo "$LINES" | jq -rs '
  [.[] | select(.t == "read")] as $reads |
  ($reads | map(.path) | unique) as $files |
  if ($files | length) == 0 then "" else
    ($files | map(split("/")[:-1] | join("/")) | unique | length) as $dirs |
    ($files | map((split("/") | length) - 1) | max) as $depth |
    "\($files | length) files · \($dirs) folders · depth \($depth)"
  end
')
if [ -z "$STATS" ]; then
  echo "🌳 tt: 0 docs consulted"
  exit 0
fi

LAST_TS=$(echo "$LINES" | jq -rs '[.[] | select(.t == "read")] | last | .ts')
LAST_PATH=$(echo "$LINES" | jq -rs '[.[] | select(.t == "read")] | last | .path')
NOW=$(date -u +%s)
THEN=$(date -ju -f "%Y-%m-%dT%H:%M:%SZ" "$LAST_TS" +%s 2>/dev/null || echo "$NOW")
AGE=$((NOW - THEN))

if [ "$AGE" -lt 90 ]; then
  DOT="●" COLOR=$'\033[1;38;5;114m'
elif [ "$AGE" -lt 600 ]; then
  DOT="◐" COLOR=$'\033[38;5;178m'
else
  DOT="○" COLOR=$'\033[38;5;245m'
fi

printf '🌳 %s %b%s %s\033[0m\n' "$STATS" "$COLOR" "$DOT" "$LAST_PATH"
