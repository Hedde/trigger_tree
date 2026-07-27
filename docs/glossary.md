# Glossary

| Term | Meaning |
|---|---|
| Heat | Current attention: timestamped reads decay with a 30-day half-life. |
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
| Never-triggered | A probe with zero opportunities in the observed period; a recurring-cost review prompt, not 0% adherence or a removal recommendation. |
