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
