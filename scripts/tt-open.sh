#!/bin/bash
# Opens the Trigger Tree live dashboard (tt-watch.py) in a new Terminal window.
# Usage: tt-open.sh [demo|replay]   (leeg = live tail van de echte history)
set -euo pipefail

MODE="${1:-}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${CLAUDE_PROJECT_DIR:-$(pwd)}"

FLAG=""
case "$MODE" in
  demo|replay) FLAG="--$MODE" ;;
  "") ;;
  *) echo "usage: tt-open.sh [demo|replay]" >&2; exit 1 ;;
esac

CMD="cd '$ROOT' && CLAUDE_PROJECT_DIR='$ROOT' python3 '$SCRIPT_DIR/tt-watch.py' $FLAG"

# Testable without opening a window.
if [ "${TT_OPEN_DRYRUN:-}" = "1" ]; then
  echo "$CMD"
  exit 0
fi

if [ "$(uname)" = "Darwin" ]; then
  osascript \
    -e 'tell application "Terminal"' \
    -e 'activate' \
    -e "do script \"$CMD\"" \
    -e 'end tell' >/dev/null
else
  echo "Not macOS — start manually in a second terminal:" >&2
  echo "$CMD" >&2
  exit 1
fi
