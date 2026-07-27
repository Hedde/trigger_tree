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

Refreshing those hashes does not discard evidence. Recorded events are bound to a
*probe fingerprint* — the declared topic set plus the `pattern_id`-to-pattern mapping —
not to the instruction prose. Rewording a rule, moving it to another line, or editing an
unrelated paragraph keeps every prior opportunity, which is what makes the before/after
trend meaningful. Changing a probe's topics or a command pattern does change the
fingerprint, and evidence recorded under the previous semantics is discarded rather than
reinterpreted.

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

`--check` always reports how many observable directives were actually measured, so a
pass backed by no evidence is visible rather than silent. Add `--min-measured N` to fail
the gate until at least N directives carry real opportunities — worth setting in CI,
since a manifest whose probe semantics just changed starts with none.

Rates remain provisional below five usable opportunities. Compaction-crossing negative
evidence is shown as degraded and excluded from the primary rate. Dataset maturity remains
independently `cold-start`, `warming`, or `mature`.

Silence is reported as one of four distinct statuses, because they mean different things:

| Status | Meaning |
|---|---|
| `never-triggered` | The rule never applied across the sessions where its capture was running. A cost/review prompt, never a removal recommendation. |
| `awaiting-capture` | No recorded session carried the signal this probe needs, so nothing can be concluded yet. Not a cost finding. |
| `no-violations-observed` | A `path_avoided` rule that held wherever it could be checked. The rule working is not evidence it is unused. |
| `capture-disabled` | The configuration required by this probe is off. Excluded from rates. |

Only `never-triggered` counts toward the always-loaded cost headline, and its denominator
is the number of sessions in which the probe's capture was actually active — never the
total session count, which would charge a directive for silence recorded before its
instrumentation existed.

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
probe fingerprint cannot become negative evidence for the new vocabulary. Hosted
tools, unsupported MCP edits, untrusted Codex hooks, directory symlinks, and compaction
can still hide evidence. See [privacy](privacy.md), [configuration](configuration.md),
and [platform support](platform-support.md).
