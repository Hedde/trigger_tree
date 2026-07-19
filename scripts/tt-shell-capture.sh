#!/usr/bin/env bash
# Runtime Bash read capture. Sourced by Claude Code's CLAUDE_ENV_FILE preamble.
# Reader commands keep their normal stdout, stderr, arguments, and exit status.

_tt_capture_reader() {
  local reader="$1"
  shift

  command "$reader" "$@"
  local tt_exit_code=$?
  if [ "$tt_exit_code" -eq 0 ] && [ -n "${TT_SHELL_LOGGER:-}" ]; then
    python3 "$TT_SHELL_LOGGER" shell-read "$reader" "$@" </dev/null >/dev/null 2>&1 ||
      python "$TT_SHELL_LOGGER" shell-read "$reader" "$@" </dev/null >/dev/null 2>&1 || true
  fi
  return "$tt_exit_code"
}

cat() { _tt_capture_reader cat "$@"; }
head() { _tt_capture_reader head "$@"; }
tail() { _tt_capture_reader tail "$@"; }
sed() { _tt_capture_reader sed "$@"; }
awk() { _tt_capture_reader awk "$@"; }
