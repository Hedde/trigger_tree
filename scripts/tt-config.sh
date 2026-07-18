# trigger-tree — default configuration.
# Override per project: create $PROJECT/.trigger-tree/config.sh with the same variables.
# Paths are relative to the project root.

# A Read of a file matching this regex counts as a documentation read.
TT_WATCH_REGEX='^(docs|agents|skills|agent-briefs)/.*\.md$|^\.claude/(rules|skills)/.*\.md$|^(CLAUDE|AGENTS)\.md$'

# A Glob/Grep whose target dir matches this regex counts as "hunting" (the model is
# searching instead of being routed — a signal the index instructions are unclear).
TT_SCAN_REGEX='^(docs|agents|skills|agent-briefs)(/|$)'

# Files matching this regex are loaded automatically (system-prompt injection, nested
# CLAUDE.md on-demand loading, Skill tool) and therefore cannot be judged through
# Read telemetry — excluded from untouched review-candidate analysis.
TT_ALWAYS_LOADED_REGEX='(^|/)(CLAUDE|AGENTS)\.md$|(^|/)CLAUDE\.local\.md$|^\.claude/skills/'

# Comma-separated globs for rare-but-critical documentation that must be reviewed,
# never treated as an archive candidate. Safety paths are protected regardless.
TT_CRITICAL_GLOB=''

# How prompt markers are recorded: hash (default, no prompt text), truncate (opt-in,
# first 200 chars), off (marker only). Task fingerprints work in all three modes.
TT_LOG_PROMPTS='hash'

# Rotate history.jsonl to history-<timestamp>.jsonl when it exceeds this many bytes.
TT_ROTATE_BYTES='5242880'
