# Instruction adherence

trigger-tree cannot tell whether an injected instruction was read: root instruction
files are loaded without a Read event. Instead it measures whether a directive changed
observable behavior:

- A **directive** is one instruction with zero or one declared **probe**.
- A probe has a deterministic trigger (an opportunity) and satisfaction predicate.
- Each session is `n/a`, `followed`, or `unobserved` for that probe.
- `unobserved` means evidence was not captured; it never means violated.

Measurement is local, deterministic, and uses zero model tokens. A model may propose
probes at authoring time, but the user must review them; it never scores adherence.

## Author a manifest

Run:

```text
/tt setup
/tt instructions --init
```

The first command explicitly enables bounded topics, classified commands, and a
conservative edit-path scope in this project. Existing installs remain off until setup
writes those keys. The second command writes `.trigger-tree/directives.json`, a
schema-versioned, human-readable scaffold. It includes SHA-256 hashes of instruction
files. Add directives, review every proposed predicate, and commit the manifest.

```json
{
  "schema": 1,
  "instruction_files": [
    {"path": "CLAUDE.md", "sha256": "64 lowercase hex characters"}
  ],
  "directives": [
    {
      "id": "route-telemetry-questions",
      "source": {"file": "CLAUDE.md", "line": 7},
      "text": "Route telemetry questions to docs/heat-model.md",
      "probe": {
        "type": "route_followed",
        "topics": ["telemetry", "heat"],
        "paths": ["docs/heat-model.md"]
      }
    }
  ]
}
```

Instruction file paths are project-relative. IDs and command `pattern_id` values are
lowercase slugs. A source may add `end_line` for cost allocation. If a hashed instruction
file changes, evaluation stops with `stale`; run `tt instructions --init`, review the
manifest again, and commit the updated hashes.

## Probe types

| Type | Opportunity | Followed evidence |
|---|---|---|
| `route_followed` | Captured prompt topics overlap `topics` | A configured `paths` entry was read in that session |
| `skill_used` | Captured prompt topics overlap `topics` | A configured skill name was invoked |
| `command_before_commit` | An observable `git commit` command | Its `pattern_id` matched an earlier successful command in the session |
| `tests_before_commit` | An observable `git commit` command | An earlier test event passed |
| `command_after_edit` | An edit path matches `when_edited` | Its `pattern_id` matched a later successful command in the session |
| `path_avoided` | An edit path matches `forbidden` | No satisfaction predicate: the matching edit is reported as unobserved |
| `unobservable` | Never | Declares honestly that the event stream cannot check the directive |

Command probes include both a stable `pattern_id` and a bounded regular-expression
`pattern`. Classified command capture records only matched IDs. Patterns reject unsafe
features that could violate the hook timeout.

## Read the result

`/tt instructions` prints the report. Use `/tt instructions --explain <id>` for recent
session-ID evidence, `--json` for automation, or `--check --min-rate 0.8` for a
deterministic threshold over locally available evidence.

Rates remain provisional below five usable opportunities. Compaction-crossing negative
evidence is shown as degraded and excluded from the primary rate. A probe with no usable
opportunity is `never-triggered`, not 0%; this is a cost/review prompt, never a removal
recommendation. A probe whose required capture is disabled is `capture-disabled` and is
excluded from rates. Dataset maturity remains independently `cold-start`, `warming`, or
`mature`.

The report also estimates always-loaded context as Unicode characters divided by four
(no tokenizer dependency), allocates directive cost using its source line span, and
shows sessions and observed days. This is a recurring-cost estimate, not a token bill.

## Capture and privacy

Capture is opt-in for existing installs:

- `TT_LOG_TOPICS=on` stores at most eight whole-word labels from a vocabulary bounded by
  repository routers and the manifest. No prompt-derived free text is stored. It behaves
  the same with `TT_LOG_PROMPTS=truncate`, `hash`, or `off`.
- `TT_LOG_COMMANDS=classified` stores only matched manifest pattern IDs;
  `full` additionally stores a bounded command line. Output is never stored.
- `TT_EDIT_REGEX` selects edits. Edit events contain only an in-project relative path,
  tool name, and event metadata—never content or diffs.

Capture that is off is loud in `tt doctor` and the report. History written under another
manifest fingerprint cannot become negative evidence for the new vocabulary. Hosted
tools, unsupported MCP edits, untrusted Codex hooks, directory symlinks, and compaction
can still hide evidence. See [privacy](privacy.md), [configuration](configuration.md),
and [platform support](platform-support.md).
