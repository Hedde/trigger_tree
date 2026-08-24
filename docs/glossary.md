# Glossary

| Term | Meaning |
|---|---|
| Heat | Attention volume: timestamped reads decay with a 30-day half-life; bars and `h` encode it. |
| Recency color | Time since the latest read: hot ≤1 day, warm ≤3, active ≤7, cool ≤30, cold older; untouched is gray. |
| Read | A tool event proving a documentation path was consulted; not proof it was understood or followed. |
| Scan / search | `scan` is the history-schema event for an explicit documentation search target; user interfaces display it as a search. Search output is never a read. |
| Untouched | A current, evaluable file with no recorded read; a review signal, never a deletion verdict. |
| Retired | A path present in telemetry but absent from the current inventory; excluded from current health and coverage. |
| Injected / always loaded | Context loaded without a Read event, including `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, rules, and imports; classified, not guessed. |
| Maturity | Evidence age/volume: `cold-start`, `warming`, or `mature`. Public badges hide grades before mature. |
| Router | A concise entry page that points an assistant to task-specific documentation. |
| Dead-path candidate | An untouched path lacking routing evidence, presented only for human review. |
| Fingerprint / cluster | A privacy-preserving task signature and groups of sessions with similar consulted paths. |
| Directive | One project instruction, identified by a stable slug and source line span in the committed manifest. |
| Probe | A user-confirmed pair of deterministic trigger and satisfaction predicates for one directive. |
| Opportunity | A session in which a probe's trigger fired and its required capture was available. |
| Followed | The opportunity's declared satisfaction evidence was observed in the same session. |
| Unobserved | An opportunity where satisfaction evidence was not captured; never a claim that the directive was violated. |
| Unobservable | A manifest-level declaration that the event stream cannot machine-check a directive. |
| Unobservable reason | Why a directive cannot be checked: `subjective-condition` (no testable trigger, so it likely never fires for the model either), or `requires-diff`, `requires-judgment`, `outside-capture` (boundaries of this tool, not defects in the rule). |
| Never-triggered | A probe with zero opportunities across the sessions where its capture was running; a recurring-cost review prompt, not 0% adherence or a removal recommendation. |
| Awaiting-capture | A probe whose required signal no recorded session carried yet; nothing can be concluded, and it is not a cost finding. |
| No-violations-observed | A `path_avoided` probe that never fired where edits were visible; the rule held, which is not evidence it is unused. |
| Persona | One subagent definition under `.claude/agents/` carrying YAML frontmatter. Prose without frontmatter is documentation, not a persona. Its name and description are injected every request; its body only when invoked, so the two costs are separate. Never-invoked is a review prompt, never a removal recommendation. |
| Probe reachability | Whether a probe can fire at all, proved by running it against evidence constructed in memory; separates a rule nobody needed from a probe nothing could ever match. |
| Probe fingerprint | The hash of declared topics and command patterns that binds recorded evidence to the semantics it was captured under; instruction prose is deliberately excluded so rewording a rule preserves its trend. |
