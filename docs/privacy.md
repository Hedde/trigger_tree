# Privacy and local data

- Runtime code makes no network calls and uses only Python’s standard library.
- Telemetry stays in the project’s gitignored `.trigger-tree/` directory.
- Read contents, search patterns/output, commands, and MCP responses are not stored.
- Installation defaults to `truncate`, so up to 200 recognizable prompt characters can be stored locally and gitignored before or without setup. `hash` stores a short stable SHA-1 fingerprint; `off` stores only a marker. Setup asks for the choice, and changes affect future prompts only.
- Deletion belongs to the user. Uninstall removes wiring but intentionally preserves telemetry.

The experimental outcome view observes local HEAD changes and test-command results. It is correlational and off by default. See the complete [privacy policy](../PRIVACY.md) and [security policy](../SECURITY.md).
