#!/usr/bin/env bash
# Runtime Bash read capture. Sourced by Claude Code's CLAUDE_ENV_FILE preamble.
# Reader commands keep their normal stdout, stderr, arguments, and exit status.

# Claude may source its environment preamble from another POSIX shell. Runtime
# function capture is intentionally Bash/zsh-only; leave the marker unset so the
# PostToolUse logger keeps its conservative literal-path fallback elsewhere.
if [ -z "${BASH_VERSION:-}" ] && [ -z "${ZSH_VERSION:-}" ]; then
  return 0
fi
export TT_RUNTIME_BASH_READS=1

_tt_capture_reader() {
  local reader="$1"
  shift

  command "$reader" "$@"
  local tt_exit_code=$?
  local tt_candidate tt_should_log=0
  if [ -z "${TT_SHELL_WATCH_SUFFIX:-}" ]; then
    tt_should_log=1
  else
    for tt_candidate in "$@"; do
      case "$tt_candidate" in
        *"$TT_SHELL_WATCH_SUFFIX")
          if [ -f "$tt_candidate" ]; then
            tt_should_log=1
            break
          fi
          ;;
      esac
    done
  fi
  if [ "$tt_exit_code" -eq 0 ] && [ "$tt_should_log" -eq 1 ] && [ -n "${TT_SHELL_LOGGER:-}" ]; then
    python3 "$TT_SHELL_LOGGER" shell-read "$reader" "$@" </dev/null >/dev/null 2>&1 ||
      python "$TT_SHELL_LOGGER" shell-read "$reader" "$@" </dev/null >/dev/null 2>&1 || true
  fi
  return "$tt_exit_code"
}

# The `function name` form is deliberately alias-safe in both Bash and zsh.
# A user's existing alias may continue to take precedence; preserving their shell
# semantics is more important than forcing telemetry for that command.
function cat { _tt_capture_reader cat "$@"; }
function head { _tt_capture_reader head "$@"; }
function tail { _tt_capture_reader tail "$@"; }
function sed { _tt_capture_reader sed "$@"; }
function awk { _tt_capture_reader awk "$@"; }
