---
name: tt
description: Run trigger-tree commands in Claude Code. Use for /tt status, watch, insights, suggestions, note, doctor, setup, or help.
disable-model-invocation: false
allowed-tools: Bash, Read, Write, Artifact
arguments:
  - subcommand
  - option
---

# /tt

Read the canonical command contract at `../../SKILL.md`, resolved relative to this
file, in full. Then execute it exactly with the supplied arguments. Do not add planning,
progress, or explanatory output beyond the format required by that contract.
