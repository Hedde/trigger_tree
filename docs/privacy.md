# Privacy and local data

- Runtime code makes no network calls and uses only Python’s standard library.
- Telemetry stays in the project’s gitignored `.trigger-tree/` directory.
- Read contents, search patterns/output, commands, and MCP responses are not stored.
- Before a project's setup, the fallback is `hash`: a short stable SHA-1 fingerprint, never prompt text. Plugin hooks are user-wide, so this protects repositories that have not chosen a mode yet. A user-wide default in `~/.trigger-tree/config.sh` (or the file `TT_USER_CONFIG` points to) can tighten this to `off` for every repository before any setup; a project's own choice always wins. `/tt setup` asks per project: `truncate` (recognizable 200-character previews, stored locally and gitignored), `hash`, or `off` (marker only). Changes affect future prompts only.
- Deletion belongs to the user. Uninstall removes wiring but intentionally preserves telemetry.

The experimental outcome view observes local HEAD changes and test-command results. It is correlational and off by default. See the complete [privacy policy](../PRIVACY.md) and [security policy](../SECURITY.md).
