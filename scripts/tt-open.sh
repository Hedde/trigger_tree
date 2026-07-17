#!/bin/bash
# Opens the Trigger Tree live dashboard (tt-watch.py) in a new terminal pane/window.
# Usage: tt-open.sh [demo|replay]   (empty = live tail of the real history)
# Tries, in order: tmux split, macOS Terminal (osascript), Windows Terminal/start
# (Git Bash), gnome-terminal, konsole, x-terminal-emulator, xterm.
set -euo pipefail

MODE="${1:-}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${CLAUDE_PROJECT_DIR:-$(pwd)}"
PY="$(command -v python3 || command -v python || echo python3)"

FLAG=""
case "$MODE" in
  demo|replay) FLAG="--$MODE" ;;
  "") ;;
  *) echo "usage: tt-open.sh [demo|replay]" >&2; exit 1 ;;
esac

CMD="cd '$ROOT' && CLAUDE_PROJECT_DIR='$ROOT' '$PY' '$SCRIPT_DIR/tt-watch.py' $FLAG"

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

case "$(uname)" in
  Darwin)
    # Stay in the terminal you called it from: iTerm2 gets a split pane in the
    # current window instead of a foreign Terminal.app window.
    if [ "${TERM_PROGRAM:-}" = "iTerm.app" ]; then
      # iTerm2's AppleScript `command` is exec-style (no shell), so a compound
      # `cd ... && ...` dies instantly and the pane closes. Hand it a launcher
      # script instead, which also keeps the pane open on failure.
      LAUNCH="$(mktemp -t tt-watch)"
      # shellcheck disable=SC2016  # $status/$0 must stay literal in the generated script
      {
        printf '#!/bin/bash\n%s\n' "$CMD"
        printf 'status=$?\n'
        printf 'if [ $status -ne 0 ]; then\n'
        printf '  echo; echo "tt-watch exited with status $status - press Enter to close"\n'
        printf '  read -r\nfi\n'
        printf 'rm -f "$0"\n'
      } > "$LAUNCH"
      chmod +x "$LAUNCH"
      if osascript \
        -e 'tell application "iTerm2"' \
        -e 'tell current session of current window' \
        -e "split vertically with default profile command \"$LAUNCH\"" \
        -e 'end tell' \
        -e 'end tell' >/dev/null 2>&1; then
        echo "Trigger Tree watcher opened in an iTerm2 split (same window)."
      else
        osascript \
          -e 'tell application "iTerm2"' \
          -e "create window with default profile command \"$LAUNCH\"" \
          -e 'end tell' >/dev/null
        echo "Trigger Tree watcher opened in a new iTerm2 window."
      fi
      exit 0
    fi
    osascript \
      -e 'tell application "Terminal"' \
      -e 'activate' \
      -e "do script \"$CMD\"" \
      -e 'end tell' >/dev/null
    echo "Trigger Tree watcher opened in a new Terminal window."
    exit 0
    ;;
  MINGW*|MSYS*|CYGWIN*)  # Windows (Git Bash)
    if command -v wt.exe >/dev/null 2>&1; then
      wt.exe new-tab bash -lc "$CMD" &
    else
      cmd.exe /c start bash -lc "$CMD" &
    fi
    echo "Trigger Tree watcher opened in a new window."
    exit 0
    ;;
esac

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
