# Platform support

| Platform | Telemetry and analysis | Watch window |
|---|---|---|
| macOS | Supported | iTerm2, tmux, or Terminal.app |
| Linux | Supported | tmux, gnome-terminal, konsole, or xterm |
| Windows | Python runtime and CI supported | Windows Terminal or `start` |

CI runs tests on all three platforms and Python 3.10–3.14. Native Windows hook launch is not exercised end to end in CI. Claude’s documented shell-free exec form is used, and the hook path requires `python3` on `PATH`; its hook condition filters tool calls, not operating systems.

## Session identity

Claude Code exports the live session id as `CLAUDE_CODE_SESSION_ID`. `CLAUDE_SESSION_ID`
is only a `${...}` placeholder that Claude Code substitutes into hook command strings, so
it never reaches the process environment. trigger-tree reads `CLAUDE_CODE_SESSION_ID`
first and falls back to `CLAUDE_SESSION_ID` and `TT_SESSION_ID` for clients or hook
wiring that do set those. Hook events themselves take the id from the payload on stdin,
so capture never depended on the variable; `tt doctor`'s current-session liveness check
did (issue #21).

Codex exports no session id at all, so its lifecycle hooks take the id from the payload
and `tt doctor` cannot identify a live Codex session. The current-session check therefore
runs on Claude Code only; under Codex the liveness line falls back to recency. To keep
that from reading as a clean bill of health, every liveness line names the clients that
have actually recorded, so telemetry from one client cannot pass as another client's
hooks working.

## Invoking the skill

Claude Code uses `/tt <command>`. Codex uses `@trigger-tree <command>`, and plain-language
requests reach the same workflows. A Codex marketplace install resolves its manifest's
`./skills/` to the repository's Claude skill, which asserts `--client claude`; the scripts
therefore treat the install location as authoritative and report `codex` regardless of the
flag, so a wrongly loaded skill cannot mislabel a session.

## Agent persona capture

Claude Code launches subagents through an `Agent` tool call whose input carries
`subagent_type`; that name is the only field recorded. Verified against real transcripts
rather than assumed, after issue #21. The Codex adapter routes `Agent` and `Task` the
same way, but whether Codex surfaces a subagent launch as a hook-visible tool call is
unverified, so treat Codex persona counts as unsupported until observed. `tt doctor`
reports persona definitions found while capture is off, so silence is never mistaken for
an unused persona.

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
