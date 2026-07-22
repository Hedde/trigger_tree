# Platform support

| Platform | Telemetry and analysis | Watch window |
|---|---|---|
| macOS | Supported | iTerm2, tmux, or Terminal.app |
| Linux | Supported | tmux, gnome-terminal, konsole, or xterm |
| Windows | Python runtime and CI supported | Windows Terminal or `start` |

CI runs tests on all three platforms and Python 3.10–3.13. Native Windows hook launch is not exercised end to end in CI. Claude’s documented shell-free exec form is used, and the hook path requires `python3` on `PATH`; its hook condition filters tool calls, not operating systems.
