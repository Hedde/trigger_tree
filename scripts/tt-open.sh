#!/bin/bash
# Opens the Trigger Tree live dashboard (tt-watch.py) in a new terminal pane/window.
# Usage: tt-open.sh [demo|replay]   (empty = live tail of the real history)
# Tries, in order: tmux split, macOS Terminal (osascript), gnome-terminal, konsole,
# x-terminal-emulator, xterm. Prints the manual command if none is available.
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

if [ -n "${TMUX:-}" ]; then
  tmux split-window -h "$CMD"
  echo "Trigger Tree watcher opened in a tmux split."
  exit 0
fi

if [ "$(uname)" = "Darwin" ]; then
  osascript \
    -e 'tell application "Terminal"' \
    -e 'activate' \
    -e "do script \"$CMD\"" \
    -e 'end tell' >/dev/null
  echo "Trigger Tree watcher opened in a new Terminal window."
  exit 0
fi

for TERM_CMD in gnome-terminal konsole x-terminal-emulator xterm; do
  if command -v "$TERM_CMD" >/dev/null 2>&1; then
    case "$TERM_CMD" in
      gnome-terminal) "$TERM_CMD" -- bash -c "$CMD" & ;;
      *) "$TERM_CMD" -e bash -c "$CMD" & ;;
    esac
    echo "Trigger Tree watcher opened via $TERM_CMD."
    exit 0
  fi
done

echo "No supported terminal found — start manually in a second terminal:" >&2
echo "$CMD" >&2
exit 1
