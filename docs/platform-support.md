# Platform support

| Platform | Telemetry and analysis | Watch window |
|---|---|---|
| macOS | Supported | iTerm2, tmux, or Terminal.app |
| Linux | Supported | tmux, gnome-terminal, konsole, or xterm |
| Windows | Python runtime and CI supported | Windows Terminal or `start` |

CI runs tests on all three platforms and Python 3.10–3.14. Native Windows hook launch is not exercised end to end in CI. Claude’s documented shell-free exec form is used, and the hook path requires `python3` on `PATH`; its hook condition filters tool calls, not operating systems.

## Instruction-adherence capture

Claude Code PostToolUse hooks capture supported `Edit`, `Write`, and `MultiEdit` calls.
Codex lifecycle hooks normalize its edit surface (`apply_patch`, `Edit`, or `Write`) into
the same path-only event. Tool availability can change by client or host: hosted tools,
unsupported MCP edit shapes, and other operations that bypass local lifecycle hooks are
invisible.

Codex also requires explicit hook trust in the interactive TUI. Until all trigger-tree
hooks are trusted, capture may be empty; non-interactive `codex exec` does not persist
that trust, and a changed hook requires review again. `tt doctor` reports these gaps.
Unavailable capture produces `capture-disabled` and is excluded from rates rather than
becoming `unobserved`.
