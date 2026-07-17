# Trigger Tree — default configuration.
# Override per project: create $PROJECT/.trigger-tree/config.sh with the same variables.
# Paths are relative to the project root.

# A Read of a file matching this regex counts as a documentation read.
TT_WATCH_REGEX='^(docs|agents|skills|agent-briefs)/.*\.md$|^\.claude/(rules|skills)/.*\.md$|^(CLAUDE|AGENTS)\.md$'

# A Glob/Grep whose target dir matches this regex counts as "hunting" (the model is
# searching instead of being routed — a signal the index instructions are unclear).
TT_SCAN_REGEX='^(docs|agents|skills|agent-briefs)(/|$)'

# Files matching this regex are loaded automatically (system-prompt injection / Skill
# tool) and can therefore never be "dead" — excluded from untouched/dead-path analysis.
TT_ALWAYS_LOADED_REGEX='^(CLAUDE|AGENTS)\.md$|^\.claude/(rules|skills)/'
