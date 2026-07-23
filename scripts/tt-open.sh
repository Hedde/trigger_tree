#!/bin/bash
# Opens the trigger-tree live dashboard (tt-watch.py) in a new terminal pane/window.
# Usage: tt-open.sh [demo|replay]   (empty = live tail of the real history)
# Tries, in order: tmux split, macOS Terminal (osascript), Windows Terminal/start
# (Git Bash), gnome-terminal, konsole, x-terminal-emulator, xterm.
set -euo pipefail

MODE="${1:-}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${TT_PROJECT_DIR:-${CLAUDE_PROJECT_DIR:-$(pwd)}}"
PY="$(command -v python3 || command -v python || echo python3)"
PLATFORM="$(uname)"
# Claude may expose a native C:\... project path while the launcher runs in Git
# Bash. Convert it before quoting so `cd` and the child environment use one form.
case "$PLATFORM" in
  MINGW*|MSYS*|CYGWIN*)
    if command -v cygpath >/dev/null 2>&1; then
      ROOT="$(cygpath -u "$ROOT")"
    fi
    ;;
esac
VERSION="$(sed -n 's/.*"version": "\([^"]*\)".*/\1/p' "$SCRIPT_DIR/../.claude-plugin/plugin.json" 2>/dev/null | head -1)"
V="v${VERSION:-?}"

FLAG=""
case "$MODE" in
  demo|replay) FLAG="--$MODE" ;;
  "") ;;
  *) echo "usage: tt-open.sh [demo|replay]" >&2; exit 1 ;;
esac

# Per-invocation plugin roots outrank the ambient CODEX_HOME: that one stays
# exported in shell profiles, so it must not relabel Claude-launched sessions.
CLIENT="${TT_CLIENT:-}"
if [ -z "$CLIENT" ]; then
  if [ -n "${PLUGIN_ROOT:-}" ]; then
    CLIENT="codex"
  elif [ -n "${CLAUDE_PLUGIN_ROOT:-}" ]; then
    CLIENT="claude"
  elif [ -n "${CODEX_HOME:-}" ]; then
    CLIENT="codex"
  else
    case "$SCRIPT_DIR" in
      */.claude/plugins/*) CLIENT="claude" ;;
      */.codex/plugins/*) CLIENT="codex" ;;
      *) CLIENT="auto" ;;
    esac
  fi
fi

make_launcher() {
  LAUNCH="$(mktemp "${TMPDIR:-/tmp}/tt-watch.XXXXXX")"
  # shellcheck disable=SC2016  # $status/$0 must stay literal in the generated script
  {
    printf '#!/bin/bash\n%s\n' "$CMD"
    printf 'status=$?\n'
    printf 'if [ $status -eq 143 ] || [ $status -eq 130 ]; then\n'
    printf '  echo; echo "tt-watch stopped: terminated from outside (signal $((status-128))) - not a crash. press Enter to close"\n'
    printf '  read -r\n'
    printf 'elif [ $status -ne 0 ]; then\n'
    printf '  echo; echo "tt-watch crashed with status $status - press Enter to close"\n'
    printf '  read -r\nfi\n'
    printf 'rm -f "$0"\n'
  } > "$LAUNCH"
  chmod +x "$LAUNCH"
}

# Build a shell-safe command. Repository names can legally contain spaces,
# apostrophes and shell metacharacters; the split must still tail that exact repo.
printf -v Q_ROOT '%q' "$ROOT"
printf -v Q_PY '%q' "$PY"
printf -v Q_WATCH '%q' "$SCRIPT_DIR/tt-watch.py"
printf -v Q_CLIENT '%q' "$CLIENT"
CMD="cd $Q_ROOT && CLAUDE_PROJECT_DIR=$Q_ROOT $Q_PY $Q_WATCH $FLAG --client $Q_CLIENT"

# Testable without opening a window.
if [ "${TT_OPEN_DRYRUN:-}" = "1" ]; then
  echo "$CMD"
  exit 0
fi

if [ -n "${TMUX:-}" ]; then
  tmux split-window -h "$CMD"
  echo "trigger-tree $V watcher opened in a tmux split."
  exit 0
fi

case "$PLATFORM" in
  Darwin)
    # Stay in the terminal you called it from: iTerm2 gets a split pane in the
    # current window instead of a foreign Terminal.app window.
    if [ "${TERM_PROGRAM:-}" = "iTerm.app" ]; then
      # iTerm2's AppleScript `command` is exec-style (no shell), so a compound
      # `cd ... && ...` dies instantly and the pane closes. Hand it a launcher
      # script instead, which also keeps the pane open on failure.
      make_launcher
      # Target the exact session that invoked us (ITERM_SESSION_ID), so two Claude
      # sessions in different projects each get their own split — never the
      # frontmost window by accident.
      SESSION_UUID="${ITERM_SESSION_ID#*:}"
      if [ -n "${ITERM_SESSION_ID:-}" ] && osascript >/dev/null 2>&1 <<OSA
tell application "iTerm2"
  set found to false
  repeat with w in windows
    repeat with t in tabs of w
      repeat with s in sessions of t
        if (id of s as text) is "$SESSION_UUID" then
          tell s to split vertically with default profile command "$LAUNCH"
          set found to true
        end if
      end repeat
    end repeat
  end repeat
  if not found then error "no matching session"
end tell
OSA
      then
        echo "trigger-tree $V watcher opened in an iTerm2 split next to this session."
      elif osascript \
        -e 'tell application "iTerm2"' \
        -e 'tell current session of current window' \
        -e "split vertically with default profile command \"$LAUNCH\"" \
        -e 'end tell' \
        -e 'end tell' >/dev/null 2>&1; then
        echo "trigger-tree $V watcher opened in an iTerm2 split (same window)."
      else
        osascript \
          -e 'tell application "iTerm2"' \
          -e "create window with default profile command \"$LAUNCH\"" \
          -e 'end tell' >/dev/null
        echo "trigger-tree $V watcher opened in a new iTerm2 window."
      fi
      exit 0
    fi
    make_launcher
    osascript \
      -e 'tell application "Terminal"' \
      -e 'activate' \
      -e "do script \"$LAUNCH\"" \
      -e 'end tell' >/dev/null
    echo "trigger-tree $V watcher opened in a new Terminal window."
    exit 0
    ;;
  MINGW*|MSYS*|CYGWIN*)  # Windows (Git Bash)
    if command -v wt.exe >/dev/null 2>&1; then
      wt.exe new-tab bash -lc "$CMD" &
    else
      cmd.exe /c start bash -lc "$CMD" &
    fi
    echo "trigger-tree $V watcher opened in a new window."
    exit 0
    ;;
esac

for TERM_CMD in gnome-terminal konsole x-terminal-emulator xterm; do
  if command -v "$TERM_CMD" >/dev/null 2>&1; then
    case "$TERM_CMD" in
      gnome-terminal) "$TERM_CMD" -- bash -c "$CMD" & ;;
      *) "$TERM_CMD" -e bash -c "$CMD" & ;;
    esac
    echo "trigger-tree $V watcher opened via $TERM_CMD."
    exit 0
  fi
done

echo "No supported terminal found — start manually in a second terminal:" >&2
echo "$CMD" >&2
exit 1
