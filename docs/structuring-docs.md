# Structuring documentation for discovery

Keep the root `CLAUDE.md` below 200 lines and use it as a task router, not a manual. Give each documentation folder one entry point (`README.md`, `_index.md`, `index.md`, or nested `CLAUDE.md`) and link every sibling that should be discoverable.

Injected files trade measurability for guaranteed context: root/nested `CLAUDE.md`, `.claude/rules`, and `@imports` are always loaded and cannot produce Read evidence. Keep them thin. Route detailed material through index pages when provable discovery matters.

Prefix templates with `_` (for example `_template.md`) so trigger-tree can classify them as intentional scaffolding. Treat suggestions as evidence-backed proposals and review each one; low traffic can mean rare but critical.
