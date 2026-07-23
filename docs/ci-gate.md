# CI gate for documentation discoverability

`tt gate` scores **static discoverability** — repository structure only, no
telemetry, deterministic on every machine. Discoverable never means discovered:
what agents actually read stays local (`/tt insights`).

## What it measures

| Component | Weight | Meaning |
|---|---|---|
| routed | 40 | folder-router members actually listed in their entry point |
| linked | 30 | evaluable docs with at least one inbound link (no orphans) |
| entry points | 20 | doc folders with a `README.md`, `_index.md`, or `index.md` |
| watch scope | 10 | markdown files covered by `TT_WATCH_REGEX` |

Folders whose members are all `SKILL.md` files are skill packages and are not
required to have an entry point. Template files (`_*.md`) are never offenders.

Every failing component names its offenders (capped at five, with a `+N more`
count): unlisted router members, orphans, folders without an entry point, and
markdown files outside the watch scope. On GitHub Actions the same verdict is
written to the run's step summary, so the score table and findings appear on the
run page without opening the log.

## What the gate does not measure

Be precise about the boundary — three layers, three tools:

1. **Instruction layer — not measured.** The gate verifies that link paths exist,
   never whether your root `CLAUDE.md` actually *instructs* agents to follow them.
   "Start at the docs router" and a passing mention of the same path score
   identically; judging prose semantics would break determinism. Whether the
   instruction works is proven by the local telemetry: a green gate with a cold
   heat map and rising search activity is the classic signal that the wiring is
   fine but the instruction fails.
2. **Root entry existence — known gap.** A repository without any root context
   file can currently score 100% while agents have no starting point at all. A
   deterministic existence check (root `CLAUDE.md`/`AGENTS.md`/`GEMINI.md`
   present and linking at least one watched doc) is a planned addition.
3. **Watch scope is a review prompt, not a defect list.** Files listed under
   "Outside the watch scope" are markdown the gate cannot see — which is often
   correct: issue templates, changelogs, and other human-only files belong
   outside the measurement. The component is capped at 10 of the 100 points for
   exactly this reason. Extend `TT_WATCH_REGEX` only for files agents should
   actually read. Reviewed a file and decided it should stay unwatched?
   Acknowledge it in `TT_SCOPE_IGNORE` (comma-separated globs in
   `.trigger-tree/config.sh`): acknowledged files leave the findings, the SARIF,
   and the denominator — visibly, in a committed and reviewable config line. A
   path the watch regex matches is never ignored.

## Usage

GitHub Actions (installs its own pinned version, runs inside your runner):

```yaml
- uses: Hedde/trigger_tree@v1.22.0
  with:
    min-score: "70"        # optional absolute floor
    badge: "discoverability.json"   # optional shields.io endpoint output
```

Any other CI:

```bash
pip install trigger-tree
tt gate --min-score 70
```

## Baseline (recommended): fail on regression, not on an arbitrary number

```bash
tt gate --update-baseline   # writes .trigger-tree/gate.json — commit it
```

With a committed baseline, the gate fails any change that lowers the score and
names the exact offending files with the edit that fixes them. Raising the bar is
deliberate: fix findings, re-run `--update-baseline`, commit. `/tt setup` keeps the
gitignore exception for `gate.json` in place.

## Machine-readable output (SARIF)

`--sarif PATH` writes a deterministic [SARIF 2.1.0](https://sarifweb.azurewebsites.net/)
report — the standard exchange format for static-analysis findings — with one rule
per category (`TTD001` unlisted router member, `TTD002` orphan, `TTD003` missing
folder entry point, `TTD004` outside watch scope; the first three are warnings, the
fourth a note) and the score, components, and verdict in the run properties. Upload
it to GitHub code scanning for per-file annotations on pull requests, or attach it
as a build artifact for any other tooling:

```yaml
- uses: Hedde/trigger_tree@v1.22.0
  with:
    sarif: "tt-gate.sarif"
- uses: github/codeql-action/upload-sarif@4187e74d05793876e9989daffde9c3e66b4acd07 # v3
  with:
    sarif_file: tt-gate.sarif
```

On GitHub Actions the verdict also lands on the run's step summary automatically.

## GitLab CI

The gate is a plain pip-installable CLI, so GitLab needs no wrapper. `--code-quality
PATH` writes a deterministic [CodeClimate](https://gitlab.com/gitlab-org/gitlab/-/blob/master/doc/ci/testing/code_quality.md)
issue list — the format GitLab renders as a Code Quality widget on merge requests,
with stable fingerprints so only new findings are announced:

```yaml
docs-gate:
  image: python:3.13-slim
  script:
    - pip install trigger-tree
    - tt gate --min-score 70 --code-quality gl-code-quality-report.json --badge public/docs-discoverability.json
  artifacts:
    when: always
    reports:
      codequality: gl-code-quality-report.json
    paths:
      - public/docs-discoverability.json
```

The committed baseline ratchet works identically. For a project badge, point a
[shields endpoint](https://shields.io/badges/endpoint-badge) at the artifact's raw
URL (`/-/jobs/artifacts/main/raw/public/docs-discoverability.json?job=docs-gate`)
in **Settings → General → Badges**. GitLab has no equivalent of the GitHub step
summary; the human-readable verdict lives in the job log.

## Exit codes

`0` pass · `1` gate failed (regression or below `--min-score`) · `2` usage or
execution error.
