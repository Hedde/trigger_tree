# Heat model and evidence boundaries

Reads are lifetime evidence and never decrease. Heat is current attention: each timestamped read contributes `0.5^(age_days / 30)`, so it halves every 30 days. Folder heat sums current file heat. Cold means inactive now, never obsolete.

The health score combines coverage, router reachability, and search behavior. Its A–F grade is provisional until the dataset is `mature` (at least 100 reads and seven observed days). Correlation is not causation: a routing change followed by fewer searches does not prove the change caused the improvement.

## What can be observed

- Native Read events, explicit Glob/Grep paths, and explicit `rg`/`grep`/`find` documentation targets.
- Expanded Bash reader paths in supported Bash sessions, preserving command behavior.
- Explicit file-like MCP parameters; never remote HTTP targets or response content.
- Subagent attribution and invoked skill names.

## Boundaries

- Injected context is invisible to Read telemetry and appears as always loaded.
- Glob/Grep counts require an explicit path or static directory prefix; scan telemetry undercounts by design.
- A read proves discovery, not comprehension, correctness, or compliance.
- Untouched and dead-path candidates are review prompts, not removal recommendations. Protected, referenced, critical, safety, and template paths remain distinct.
- Hosted tools that bypass local lifecycle hooks are invisible. Other local tools can use the documented ingest entry point.
- The health grade scores **evaluable docs** — always-loaded context is excluded
  by design, and the structural inventory follows git's view of the repository
  (tracked plus untracked-but-not-ignored files).
- Directory symlinks are never followed: a watched surface behind one stays
  outside the inventory and the score. Such surfaces are named explicitly —
  `unfollowed_surfaces` in the stats payload, a warning in `tt doctor`, and a
  health driver — so a low score is never mistaken for a verdict on knowledge
  the measurement cannot see.

See the [glossary](glossary.md) for canonical definitions.
