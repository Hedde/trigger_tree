# trigger-tree project overrides for the trigger_tree repository itself.
# Only the keys set here differ from the plugin defaults.

# The Codex workflow contract is agent documentation too: watch codex-skills/.
TT_WATCH_REGEX='^(docs|agents|skills|codex-skills|agent-briefs)/.*\.md$|^\.claude/(rules|skills)/.*\.md$|^(CLAUDE|AGENTS|GEMINI)\.md$'

# Acknowledged as intentionally unwatched: human-facing files, GitHub UI
# templates, and local (gitignored) submission drafts. Agents are steered via
# CLAUDE.md and docs/ instead.
TT_SCOPE_IGNORE='.github/*,CHANGELOG.md,CODE_OF_CONDUCT.md,CONTRIBUTING.md,PRIVACY.md,README.md,SECURITY.md,dist-submissions/*'
