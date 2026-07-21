# trigger-tree — default configuration.
# Override per project: create $PROJECT/.trigger-tree/config.sh with the same variables.
# Paths are relative to the project root.

# A Read of a file matching this regex counts as a documentation read.
TT_WATCH_REGEX='^(docs|agents|skills|agent-briefs)/.*\.md$|^\.claude/(rules|skills)/.*\.md$|^(CLAUDE|AGENTS)\.md$'

# A Glob/Grep whose explicit target dir matches this regex counts as search activity.
# The event records that a search happened, not why it happened or whether routing failed.
TT_SCAN_REGEX='^(docs|agents|skills|agent-briefs)(/|$)'

# Files matching this regex are loaded automatically (system-prompt injection, nested
# CLAUDE.md on-demand loading, Skill tool) and therefore cannot be judged through
# Read telemetry — excluded from untouched review-candidate analysis.
TT_ALWAYS_LOADED_REGEX='(^|/)(CLAUDE|AGENTS)\.md$|(^|/)CLAUDE\.local\.md$|^\.claude/skills/'

# Comma-separated globs for rare-but-critical documentation that must be reviewed,
# never treated as an archive candidate. Safety paths are protected regardless.
TT_CRITICAL_GLOB=''

# Plugin fallback: hash, so installing without /tt setup never stores prompt text.
# Setup writes truncate (first 200 local characters) into the project copy by default;
# hash and off remain explicit alternatives.
TT_LOG_PROMPTS='hash'

# Rotate history.jsonl to history-<timestamp>.jsonl when it exceeds this many bytes.
TT_ROTATE_BYTES='5242880'

# Experimental, correlational view joining reads with local session outcomes.
# Values: off (default) or on. This never makes causal claims or sends data anywhere.
TT_EXPERIMENTAL_OUTCOMES='off'
