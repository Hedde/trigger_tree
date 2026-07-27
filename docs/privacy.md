# Privacy and local data

- Runtime code makes no network calls and uses only Python’s standard library.
- Telemetry stays in the project’s gitignored `.trigger-tree/` directory.
- Read contents, search patterns/output, MCP responses, edit contents/diffs, and command
  output are not stored.
- Before a project's setup, the fallback is `hash`: a short stable SHA-1 fingerprint, never prompt text. Plugin hooks are user-wide, so this protects repositories that have not chosen a mode yet. A user-wide default in `~/.trigger-tree/config.sh` (or the file `TT_USER_CONFIG` points to) can tighten this to `off` for every repository before any setup; a project's own choice always wins. `/tt setup` asks per project: `truncate` (recognizable 200-character previews, stored locally and gitignored), `hash`, or `off` (marker only). Changes affect future prompts only.
- Deletion belongs to the user. Uninstall removes wiring but intentionally preserves telemetry.

The experimental outcome view observes local HEAD changes and test-command results. It is correlational and off by default. See the complete [privacy policy](../PRIVACY.md) and [security policy](../SECURITY.md).

Instruction adherence adds three explicit, independently controlled capture surfaces.
All default to off for an existing install with no configuration:

- `TT_LOG_TOPICS=on`: up to eight whole-word topic labels drawn only from the
  repository's router/manifest vocabulary. No prompt-derived free text reaches disk,
  regardless of `TT_LOG_PROMPTS`.
- `TT_LOG_COMMANDS=classified`: only stable IDs of manifest patterns that matched.
  `full` additionally stores a bounded command line; neither mode stores output.
- `TT_EDIT_REGEX`: matching edits store only normalized in-project path, tool name, and
  event metadata. External paths, content, arguments unrelated to paths, and diffs are
  not retained.

The committed `.trigger-tree/directives.json` is configuration, not telemetry. It
contains instruction paths and hashes, source references, optional directive text, and
user-confirmed probes. Local analysis reads instruction content to verify hashes and
estimate cost, but does not copy that content into event history or send it anywhere.
