# Changelog

## 1.17.0 — 2026-07-22

- Publishes an example insights report on the website, generated from fixed
  synthetic telemetry by a committed `make demo-report` generator and clearly
  labeled as demo data on the page itself; real reports remain local-only.
- Stops the `/tt suggestions` skill from repeating output the tool result already
  shows: the script gains `--no-apply-prompt`, the Claude contract now answers
  with a single apply-question line, and protected-summary reasons aggregate
  reference counts as "heavily referenced" instead of listing every count.

## 1.16.0 — 2026-07-22

- Restructures `/tt suggestions` into tiers: at most five numbered, appliable router
  edits (verified add-link gaps, unlisted router members, missing folder entry
  points, each with evidence numbers), up to two unnumbered "Worth a look"
  observations for telemetry signals that need judgment, and one summary line for
  low-read but likely-critical files — the apply-prompt now appears only when at
  least one numbered edit exists.
- Classifies `.claude/rules/**` as always-loaded context: Claude Code injects rules
  into the system prompt, so Read telemetry can never observe them and they no
  longer appear as untouched review candidates.
- Skips template files in unlisted-member proposals, deduplicates the same path
  across suggestion categories, guards empty folders out of cold-folder lines, and
  marks warming-stage telemetry observations as early signals.

## 1.15.1 — 2026-07-22

- Fixes a Codex dashboard regression where the detached watcher could bind to the
  installed plugin directory instead of the user's project, showing zero telemetry
  while events were being recorded correctly: every entry script and the launcher
  now honor an explicit `TT_PROJECT_DIR`, and the Codex skill contract runs all
  commands from the project directory with that override set, never from the
  plugin root.

## 1.15.0 — 2026-07-22

- Replaces the README hero with a real terminal recording of the live dashboard
  (regenerable via `make demo-gif` and the committed VHS tape) and embeds the same
  footage as a compact self-hosted video on the website, clearly labeled against
  the interactive mock demo.
- Adds one-click copy buttons to the website install blocks and documents the
  `uvx --from trigger-tree tt` zero-install route beside `pipx` in the README and
  on the site; the site remains free of external requests.

## 1.14.1 — 2026-07-22

- Brings the website demo to parity with the real dashboard controls: the
  advertised `[s]` settings panel now opens and switches the demo's prompt-privacy
  mode for future prompts, maintenance tips rotate on the real 30-second cadence,
  recently active folders bubble to the top of the focus sort and settle back
  after eight seconds, and always-loaded context appears with its `injected`
  label instead of being omitted.

## 1.14.0 — 2026-07-22

- Ships trigger-tree as a standalone PyPI package: `pipx install trigger-tree`
  provides a `tt` console command dispatching to the same bundled scripts and hook
  manifests, for CI use, git-hook ingestion, and dashboards without a plugin.
- Publishes to PyPI automatically on version tags through trusted publishing (OIDC,
  no stored secrets) after tests and release integrity pass; release integrity now
  also verifies the packaged version, and the README, site, and development docs
  document the standalone install.

## 1.13.0 — 2026-07-22

- Publishes GitHub release notes automatically from the changelog on every version
  tag: idempotent create-or-update, normalized `vX.Y.Z` titles, and a fixed install
  footer after tests and release integrity pass.
- Adds search presence to the static site — a canonical URL, SoftwareApplication
  structured data, a sitemap and robots file, and three honestly phrased common
  questions — with zero new external requests.
- Keeps distribution submission drafts and the weekly scout prompt as local,
  gitignored material; automated community posting remains explicitly out of scope.

## 1.12.0 — 2026-07-22

- Records that installation may store a recognizable, gitignored 200-character
  prompt preview before setup, and states that behavior plainly across the README,
  site, FAQ, privacy, and security docs.
- Recognizes root `GEMINI.md` alongside `CLAUDE.md` and `AGENTS.md`, and classifies
  root or nested Gemini context as injected/always loaded rather than an untouched
  candidate; `index.md` remains an ordinary folder router.
- Adds a CI and tag-time documentation-currency guard for command parity, top
  changelog/version parity, and relative-link integrity, with induced-drift tests.
- Removes the obsolete hidden setup flag, standardizes visible search terminology,
  recompresses the report capture, and verifies the recent release-tag integrity
  chain and tracked-artifact hygiene.

## 1.11.1 — 2026-07-22

- Makes recognizable, locally stored 200-character prompt previews the consistent
  plugin and runtime default instead of falling back to hashed prompts before setup.
- Asks new interactive setups to choose `truncate`, `hash`, or `off`, recommends
  `truncate`, keeps automation non-blocking, and preserves existing project choices
  unless a mode is passed explicitly.
- Updates both Claude and Codex setup workflows to ask for the privacy choice and
  pass it explicitly, with matching configuration and security documentation.

## 1.11.0 — 2026-07-22

- Turns the local insights output into a self-contained evidence report with a
  grade-first hierarchy, compact navigation, generation metadata, and the same
  section order as `/tt insights`, while retaining every underlying table.
- Adds pure-Python SVG sparklines, separate count and ratio trend charts, neutral
  note ticks, small-sample dashes, and a maturity-gated indented documentation tree;
  cold-start, single-bucket, outlier, long-name, and 100+-file cases are covered.
- Validates the shared five-step heat palette under protan, deutan, and tritan
  simulations in CI, and flattens report and site treatments to avoid decorative
  rails, rounded evidence cards, and other visual noise.
- Saves an inspected render of the generated report for documentation reuse while
  deliberately retaining the clearer synthetic dashboard demo instead of claiming
  mock footage is a real terminal recording.
- Moves docs-health badge publication to an explicit local-evidence command,
  `make badge-publish`; CI now updates measured coverage without overwriting that
  local aggregate with a permanently immature checkout result.

## 1.10.0 — 2026-07-22

- Reframes the project around its measurable documentation-discovery loop with a
  short demo-first README, a routed reference tree, canonical glossary, and concise
  root `CLAUDE.md`, while preserving every measurement and platform caveat.
- Adds `/tt badge` and `tt-stats.py --badge`, which atomically write a shields.io
  endpoint and publish only `measuring…` until the dataset is mature; CI now carries
  both coverage and docs-health endpoints on the badges branch.
- Makes empty dashboards explain how evidence appears, aligns the HTML report with
  the product heat palette and grade-first hierarchy, and adds mature cached grades
  to the statusline without recomputing stats on every refresh.
- Keeps the interactive mock TUI as the canonical demo, adds an optimized static
  dashboard capture and regenerable VHS tape, and gives the site an honest health
  story, comparison positioning, privacy statement, accessible contrast, and
  reduced-motion-safe additions.
- Adds a 1200×630 social card plus Open Graph and Twitter metadata, with no external
  site requests or analytics, and corrects cross-platform badge tests discovered by
  the full Windows CI matrix.

## 1.9.1 — 2026-07-22

- Fixes a critical v1.9.0 regression where Claude Code could load both bundled hook
  files and double-record session, prompt, and test events. Explicit client markers
  now make the Codex hook file a silent no-op under Claude while preserving stale-file
  compatibility and tool-event idempotency.
- Makes the test suite hermetic when trigger-tree's own shell-capture variables are
  present in the developer environment; the hostile-environment run remains at 100%
  coverage.
- Restores `/tt` to explicit user invocation and documents that Windows Claude hooks
  require a `python3` command on `PATH`, because the documented hook schema has no
  operating-system condition for exec-form handlers.

## 1.9.0 — 2026-07-22

- Consolidates Claude telemetry behind its declared hook manifest, routes both clients
  through one adapter, and suppresses duplicate tool events with a bounded per-session
  idempotency window.
- Uses Claude's documented shell-free hook execution across platforms and separates the
  Claude `/tt` contract from the Codex-only `trigger-tree` skill package.
- Audits the effective documentation watch scope during setup and doctor runs, proposes
  observed-layout regexes without applying them implicitly, and distinguishes static
  hook-file integrity from current, recent, stale, or never-seen hook activity.
- Counts conservative static directory prefixes for pathless Glob and Grep file-glob
  calls, keeps direct Claude and Codex events in one git-root dataset, and broadens MCP
  capture while retaining explicit local-file and non-HTTP filtering.
- Adds `/tt uninstall` to remove only trigger-tree's copied statusline and registration;
  telemetry data and gitignore entries always remain for explicit manual deletion.
- Updates the README, command contracts, packaging smoke checks, and website to describe
  the verified behavior and native Windows hook-execution boundary accurately.

## 1.8.3 — 2026-07-21

- Prevents report and session-cache symlink escapes: HTML reports are written through
  private atomic files, project-controlled symlink parents are refused, and lock/cache
  paths no longer follow links outside the repository.
- Keeps runtime shell capture correct and cheap: reads after `cd` resolve from the real
  working directory, unsupported POSIX shells retain fallback telemetry, and irrelevant
  reader commands avoid starting Python when the watched extension is known.
- Uses safe launcher files for Terminal.app paths containing quotes, and consistently
  prefers Codex-native client markers over Claude compatibility aliases. Launcher
  creation uses one portable template across BSD/macOS and GNU/Linux `mktemp`.
- Rejects structurally corrupt current-schema events instead of crashing reports, and
  excludes symlinked documentation and history files from local analysis.
- Bounds co-read pair generation and watcher prompt state, streams watcher startup
  history, and avoids rescanning every archive for genuinely new sessions.
- Clarifies that hooks store paths and metadata while selected documentation content is
  read only for local analysis and is never stored in telemetry or uploaded.
- Exercises symlink-refusal regressions through portable metadata simulations on every
  CI platform, including Windows environments without symlink privileges.

## 1.8.0 — 2026-07-21

- Reconciles every current-coverage denominator: the inventory is explicitly split
  into evaluable and always-loaded files, and touched plus untouched always equals the
  evaluable total.
- Separates retired telemetry paths from current heat, coverage, and health while
  retaining their historical reads and per-agent attribution; folder summaries add a
  measured retired-read share and median current-file age.
- Classifies a discovered folder router as a router even when its filename starts with
  an underscore, reports unread routers directly, and uses one full reference graph for
  both inbound counts and displayed samples.
- Compresses untouched review into one ranked table with folded detail and one caveat,
  hides redundant heat windows and empty folder rows, labels small trend samples, and
  exposes main-versus-subagent reads in the current heat table.
- Filters client-injected envelopes and command-only noise from task-cluster examples,
  falling back to the latest real user prompt or no example at all.

## 1.7.1 — 2026-07-21

- Makes insights proposals evidence-thresholded rather than quota-shaped: zero is a
  valid result, and every proposed link must be re-verified against two existing files
  and an absent router reference.
- Adds direct folder-router coverage using the repository's actual `README.md`,
  `_index.md`, `index.md`, or `CLAUDE.md`; unrelated in-links no longer hide files that
  are absent from their own folder entry point.
- Reclassifies scans as non-causal search activity with tool mix, session reach,
  maximum-session share, and concentrated/distributed patterns. Concentrated bulk work
  no longer creates router suggestions or lowers the documentation health score.
- Updates the HTML report, README, website, and live terminology to explain the tighter
  evidence boundaries without adding any project-specific context.

## 1.6.5 — 2026-07-21

- Excludes injected instruction files and injected-only folders from cold sorting;
  always-loaded context remains visible in focus/name views without being mislabeled
  as untouched or cold.
- Preserves the explicit Claude/Codex tip identity and cache-path fallback from the
  unreleased 1.6.4 candidate.

## 1.6.4 — 2026-07-21

- Fixes empty dashboard tips by passing Claude/Codex identity explicitly from each
  command contract into the detached watcher process.
- Adds installed-cache-path detection as a fallback plus regression coverage for both
  Claude and Codex launch paths.

## 1.6.3 — 2026-07-21

- Keeps the live dashboard footer visible when a busy tree overflows the terminal:
  the rotating tip, sort controls, and navigation help can no longer be clipped by
  the generated `files hidden` and focused-folder summary rows.
- Adds a crowded-dashboard regression fixture covering the exact failure mode.

## 1.6.2 — 2026-07-21

- Moves maintenance tips into the live dashboard as a quiet, deterministic line that
  rotates every 30 seconds; Claude and Codex receive only their own relevant guidance.
- Keeps `/tt tips` available for direct use but removes it from the prominent command
  overview. The statusline remains stable and dedicated to current telemetry.
- Passes client identity through every terminal launcher and adds regression coverage
  for detection, rotation, prompt-history suppression, and launcher quoting.

## 1.6.1 — 2026-07-21

- Fixes every Claude `/tt` subcommand resolving scripts relative to the nested command
  skill instead of the plugin root. `/tt watch` now opens directly without a failed
  command and filesystem search first.
- Extends source and isolated-install regression checks so every documented command
  references a real packaged script through `CLAUDE_PLUGIN_ROOT`.

## 1.6.0 — 2026-07-21

- Distinguishes injected instruction context from thermal activity: `CLAUDE.md`,
  `AGENTS.md`, and configured always-loaded paths are labeled `injected` and cannot
  misleadingly appear as cold documentation.
- Adds in-dashboard prompt privacy settings (`s`) with atomic, symlink-safe updates;
  makes `n` genuinely toggle A–Z/Z–A and aligns root/nested heat columns exactly.
- Makes the live watcher bounded by file count, preserves partial JSONL appends, and
  reduces inventory walks without sacrificing deletion detection.
- Keeps statusline totals across history rotation through private per-session summaries,
  serializes concurrent hook writes, and avoids rescanning the growing history on every
  refresh.
- Hardens telemetry against symlink writes and terminal escape injection, makes setup
  writes atomic, applies private permissions, and preserves Bash/zsh reader aliases.
- Adds Python fallback without retrying failed hooks and expands regression coverage for
  every behavior above across the supported platforms.

## 1.5.0 — 2026-07-21

- Makes prompt history recognizable after setup: `/tt setup` now creates a project
  config using local, gitignored 200-character previews. `/tt setup hash`, `truncate`,
  and `off` explicitly switch modes; existing history is never rewritten.
- Preserves the privacy-safe installation boundary: before setup, or without a readable
  project config, prompt logging still falls back to hashes and stores no prompt text.
- Reworks dashboard temperature into a coherent blue → cyan → green → amber → red
  spectrum. Untouched stays neutral gray, folder colors reflect aggregate heat, and a
  permanent adaptive heat legend separates temperature from lifetime read counts.
- Updates the README, privacy policy, Claude/Codex workflows, and website demo while
  preserving the website's six-card, three-column desktop USP grid.

## 1.4.0 — 2026-07-21

- Adds concise, read-only maintenance tips with strict client separation: Claude Code
  receives `/memory`, CLAUDE.md, and scoped-rule guidance; Codex receives AGENTS.md and
  reproducible-environment guidance. Neither client sees advice for the other.
- Grounds tips in repository evidence such as missing or oversized instruction files,
  unscoped Claude rules, and absent Codex verification commands. Output is deterministic,
  bounded to four tips, and never edits instruction or memory files automatically.
- Documents the official Anthropic and OpenAI guidance behind the recommendations and
  adds `/tt tips` to the Claude command and equivalent Codex natural-language workflow.

## 1.3.2 — 2026-07-20

- Restores Claude Code startup and `/tt` discovery after the withdrawn v1.3.1 package:
  shared hooks now use the Claude-compatible plugin-root variable that Codex also
  provides, and the Claude command has an explicit conventional `skills/tt/SKILL.md`.
- Prevents duplicate shared Claude events while retaining Claude-only skill, failure,
  and session-end telemetry. Codex-only Stop outcomes no longer run in Claude.
- Adds installed-package regression checks for the command skill and hook environment.

## 1.3.1 — 2026-07-20

- Clearly separates Claude Code and Codex installation, invocation, hooks, and
  statusline behavior in the README and website.
- Explains that direct GitHub marketplace installation is immediately usable but is
  distinct from an OpenAI Curated listing, which requires submission and review.
- Keeps the website's six USP cards in the fixed three-column desktop grid.

## 1.3.0 — 2026-07-20

- Adds a native Codex plugin manifest, marketplace catalog, trigger-tree skill, and
  lifecycle hooks while retaining the existing Claude Code plugin in the same repo.
- Normalizes Codex unified-exec `cmd` payloads, native reads, and filesystem MCP reads
  into the shared telemetry schema. Repository-root resolution keeps one dataset when
  Codex starts in a nested directory; hook failures remain silent and non-blocking.
- Documents and tests both installation paths. The website remains exactly six USP
  cards in a three-column desktop grid.

## 1.2.2 — 2026-07-20

- Keeps the v1.2.1 dedicated sort-legend fix while replacing the replay integration
  test's wall-clock race with a deterministic clock. Slow or suspended macOS runners
  can no longer miss the replay branch and report platform-specific 99.8% coverage.
- v1.2.1 was withdrawn because its tag CI was not fully green. v1.2.2 is the first
  valid release of the permanent wide/compact dashboard sort legend.

## 1.2.1 — 2026-07-20

- Moves the live sort controls onto a permanent dedicated legend row instead of
  sharing space with the heartbeat. Wide panes show `[f] focus`, `[h] hot`,
  `[c] cold`, and `[n] A–Z`; narrow panes get an equally complete compact legend.
- Keeps the active `sort:<mode>` visible and moves prompt navigation, quit, and
  heartbeat state to their own row, so no sort key disappears in normal split panes.

## 1.2.0 — 2026-07-20

- Makes historical prompts identifiable without weakening the privacy default:
  hashed prompts show their stable short ID, marker-only prompts say text is off,
  and opt-in truncated prompt previews expand with the terminal up to 120 characters.
- Replaces vertical spark glyphs with comparable horizontal five-cell heat bars and
  moves the heat/lifetime column to the available right edge, making better use of
  wide split panes while retaining safe narrow-pane truncation.
- Adds explicit live sorting: `f` recent-focus, `h` hottest, `c` coldest (including
  untouched inventory), and `n` A–Z. The footer always exposes the keys and active
  mode; prompt browsing remains a separate bounded chronological timeline.
- Updates the README, plugin help, and six-card/three-column interactive website
  demo to match the new dashboard behavior.

## 1.1.0 — 2026-07-20

- Separates current documentation attention from lifetime popularity. Every
  timestamped read now contributes exponentially decaying heat with a 30-day
  half-life, while lifetime reads and last-read evidence never disappear.
- Adds deterministic 7-, 30-, and 90-day windows plus file and folder heat to the
  stats contract and HTML report. Future clock skew is bounded; undated legacy
  reads remain in lifetime totals without being presented as current heat.
- Updates the live watcher to color and sort by current heat while showing heat and
  lifetime counts side by side. Prompt browsing remains an exact per-prompt view.
- Makes the watcher a true full-screen TUI: it clears inherited scrollback, disables
  autowrap while active, and restores the terminal on every exit, preventing refresh
  frames from accumulating above the dashboard.
- Updates the plugin instructions, README, and six-card/three-column website example
  to explain the temporal model and its safety boundary: cold means inactive now,
  never unimportant or safe to remove.

## 1.0.4 — 2026-07-19

- Fixes an urgent zsh compatibility regression in the runtime reader wrapper:
  `status` is a read-only zsh parameter, so assigning it after a successful reader
  command skipped telemetry and changed the command result to exit 1. The wrapper
  now uses a private, shell-neutral exit-code variable.
- Runs the exact variable/command-substitution/loop capture regression in both bash
  and zsh, proving that reader output and exit status remain unchanged while expanded
  documentation paths are recorded.

## 1.0.3 — 2026-07-19

- Captures the expanded runtime arguments of successful Bash `cat`, `head`, `tail`,
  non-mutating `sed`, and `awk` calls. Documentation reads through variables,
  command substitutions, loops, and shell globs now produce exact file-level read
  events without storing commands, output, patterns, or contents.
- Installs the capture functions through Claude Code's session-scoped environment
  preamble without rewriting commands or changing permissions. Environments without
  Bash retain the conservative literal-path parser, and PostToolUse suppresses
  duplicate reads when runtime capture is active.
- Updates the README, privacy contract, and website copy. The website remains six
  USP cards in a fixed three-column desktop grid with responsive two/one-column
  fallbacks.

## 1.0.2 — 2026-07-19

- Keeps the statusline live for scan-only discovery: scan events now participate in
  freshness and latest-path display, render as folder paths with a trailing slash,
  and get their own counter while file/folder/depth totals remain read-derived.
- Records existing watched documentation files consumed by Bash `cat`, `head`,
  `tail`, non-mutating `sed`, and `awk` commands as ordinary file-level reads.
  Multiple file arguments are preserved; `sed -i` variants and non-doc files are
  ignored. End-to-end coverage proves these reads flow through the live watcher.

## 1.0.1 — 2026-07-19

- Makes the advertised critical-tag and widely-linked safety protections explicit,
  isolated regression contracts. Critical tags are verified without another
  protection as a fallback; widely-linked docs are verified at the three-in-link
  threshold. Both must remain protected, rare-but-critical review items.

## 1.0.0 — 2026-07-19

- Promotes the verified 1.0 release-candidate contract to stable: context-aware
  always-loaded classification, safe rare-critical review candidates, history
  schema migration, hardened diagnostics, and the opt-in experimental outcome view.
- The stable tag is held to the same Linux/macOS/Windows, Python 3.10–3.13,
  100%-coverage, formatting, shell, workflow-security, plugin-install, and
  release-integrity gates used for the release candidate.

## 1.0.0-rc.1 — 2026-07-19

- Recursively resolves the `CLAUDE.md` `@import` graph and classifies injected files
  as always-loaded instead of cold. Subagent reads retain `agent_id`/`agent_type`,
  while stable tool-call IDs prevent replayed events around compaction from inflating
  counts.
- Reframes untouched documentation as review candidates. Always-loaded files,
  safety paths, high-in-link documents, configured critical globs, critical tags,
  and templates are protected with an explicit likely-keep explanation and a
  rare-but-critical caveat.
- Adds history schema version 1. Legacy schema-less events migrate explicitly in
  memory; unknown future versions are rejected and surfaced rather than misread.
- Expands `/tt doctor` with exact hook-route, config, supported-Python, rotated-log,
  corrupt-line, legacy-migration, and future-schema diagnostics. Rotation now keeps
  every archive even when multiple rotations happen in the same second.
- Adds an opt-in `TT_EXPERIMENTAL_OUTCOMES='on'` view joining documentation reads
  with local commit and test-command signals. It is labeled correlational—not causal—
  and remains disabled by default.

## 0.8.0 — 2026-07-18

- **Trustworthy compatibility contract:** supported end-user runtimes are now the
  security-supported Python 3.10–3.13 range, verified independently in CI alongside
  the Ubuntu, macOS, and Windows test matrix and a strict 100% coverage gate.
- Added Black and Ruff gates, pinned development/test dependencies, and documented a
  venv-only contributor workflow. Runtime hooks remain dependency-free stdlib Python.
- Added actionlint and zizmor workflow audits, immutable action pins, least-privilege
  job permissions, and Dependabot coverage for Actions, Python, and npm dependencies.
- Claude plugin validation now uses a locked CLI on Node 22, rejects incomplete npm
  installs, and proves a real marketplace install inside an isolated Claude config.
- Release tags now fail CI unless the tag, plugin manifest, marketplace, and changelog
  agree. README and website trust claims now describe the gates that actually run.

## 0.7.5 — 2026-07-18

- **Privacy-hardened prompt markers:** the default is now `hash`, so prompt text is
  never stored unless a project explicitly opts in to `truncate`. `off` remains
  available for marker-only telemetry; existing project overrides keep their choice.
- Clarified that trigger-tree records local telemetry but sends nothing off-device,
  and aligned plugin, marketplace, README, security, privacy, and website copy around
  “See which docs your AI actually discovers.”

## 0.7.4 — 2026-07-18

- The live overview is now focused on at most ten folders with proven activity:
  recent activity first, then cumulative reads/searches. Untouched folders and
  files collapse into one quiet/unread summary instead of filling the viewport.
- Prompt-history remains exact and `/tt insights` retains the complete cold-path
  inventory, so focus does not discard evidence.

## 0.7.3 — 2026-07-18

- The live dashboard now brings the currently active and recently touched folders
  to the top of the viewport. After eight seconds they return to deterministic
  alphabetical order; files inside each folder never jump around.
- Prompt-history views remain strictly alphabetical for predictable comparison.

## 0.7.2 — 2026-07-18

- Updated the CI toolchain to the current Node 24-based GitHub Actions majors:
  `actions/checkout@v7`, `actions/setup-python@v6`, and `actions/setup-node@v7`.
  This removes the Node 20 deprecation warnings from every CI job.

## 0.7.1 — 2026-07-18

- **Deleted docs no longer haunt the live tree.** Historical Read events retain
  their counters but cannot re-add a path that no longer exists; historical scans
  of removed folders likewise stay out of the live overview.
- The watcher refreshes its documentation inventory every second, so a file or
  folder removed while the pane is open disappears without a restart. Prompt
  history still shows the original evidence when browsing ←/→.

## 0.7.0 — 2026-07-18

- **Folders no longer look untouched while being searched.** Every folder row now
  keeps `🔍 N searches` separate from `N unread`: scans increase the first counter;
  only actual Read events lower the second. Scan-only prompts get a visible folder
  row, and ←/→ browsing recalculates both signals for the selected prompt.
- **Concise `/tt suggestions`.** A deterministic formatter captures full stats
  internally and writes only its evidence scope plus at most five prioritized
  router edits to stdout. It explicitly says nothing changes until confirmation;
  cold-start and no-finding states stay one or two lines.
- The interactive website demo mirrors the new folder counters.

## 0.6.2 — 2026-07-18

- **End-to-end proof for Bash discovery telemetry.** A cross-process regression
  test now proves the complete live progression: the watcher starts at
  `0 reads · 0 scans`, an external Bash hook moves it to `0 reads · 1 scan`, and
  only a later Read hook moves it to `1 read · 1 scan`.
- The hook manifest itself is regression-tested, ensuring Bash, native search/read,
  and Skill events cannot silently lose their logger route.
- Arrow escape decoding now tolerates briefly delayed bytes on loaded terminals;
  the previous 30 ms window proved flaky on a macOS CI runner and could recreate
  the same ignored/right-arrow symptom under local system load.
- Cross-platform CI now runs every matrix leg even if another platform fails, so
  release evidence is complete rather than hidden by fail-fast cancellation.

## 0.6.1 — 2026-07-18

- **Bash doc searches are visible.** PostToolUse telemetry now recognizes executed
  `rg`, `grep`, and `find` command segments when they explicitly target existing
  documentation paths. They appear as scans, never reads, so the live prompt view
  no longer reports `0 scans` while the transcript visibly contains `rg` lookups.
- Classification is deliberately conservative and private: commands, patterns,
  output, nonexistent paths, source-code searches, and quoted mentions of `rg` are
  not logged. Repeated search segments targeting the same folder in one Bash call
  produce one scan.

## 0.6.0 — 2026-07-17

- **Prompt navigation is directional and predictable.** ← always moves older and
  → always moves newer; both ends clamp instead of wrapping or changing mode, and
  `a` explicitly returns to the live overview. The input decoder now also handles
  fragmented, application-cursor, and modified arrow escape sequences atomically.
- **`/tt doctor` removes setup guesswork.** One command verifies the hook manifest,
  local-data gitignore, optional statusline, and valid telemetry in the invoking
  repository, with a concrete recovery action for each problem.
- **Real-time means the invoking repo, without path exceptions.** The split launcher
  safely handles spaces, apostrophes, and shell metacharacters. Cross-process tests
  prove a running watcher displays hook events appended after startup and remains
  bound to the exact repository.
- **100% is now the release floor.** CI raises its cross-platform coverage gate from
  80% to 100%.

## 0.5.3 — 2026-07-17

- **Fix: both arrow keys browsed backwards.** The key loop mixed `select()` on
  the raw fd with buffered `sys.stdin.read()`: the buffered read slurped the
  whole escape sequence, the follow-up `select()` saw an empty fd, and the
  leftover `[` replayed on the *next* keypress — so ← and → both acted as
  "prev", one press late. Keys are now read raw via `os.read()` (`read_key()`),
  with a pipe-based regression test.

## 0.5.2 — 2026-07-17

- **Arrow keys** now browse prompts too (←/→ on macOS/Linux escape sequences and
  Windows console codes), and the hint lines say so in plain words
  ("←/→ browse per prompt"). Fixes a truncation assertion in the 0.5.1 test run.
- **Bounded prompt detail**: the browser keeps the last 20 prompts (500 events
  each) while dashboard totals keep aggregating the full history — endless
  sessions can't grow memory.
- **Website demo** now demonstrates per-prompt browsing with ←/→ as well.

## 0.5.1 — 2026-07-17

- **Typed prompts are now instantly visible in the live view**: every prompt
  appears in the ticker (`▸ "…"`) the moment you hit enter, and the footer counts
  prompts alongside reads — so "5 prompts · 0 reads" self-explains an
  injected-context session instead of looking stale.

## 0.5.0 — 2026-07-17

- **Per-prompt browsing in the dashboard**: `[` and `]` step through every typed
  prompt; the tree filters to exactly what that input aggregated (reads, scans,
  skill uses) with the prompt text in the header; `a` returns to live. Reads
  before the first prompt land in a "(session start)" bucket.
- **End-to-end regression guard**: a test now spawns the watcher and the logger as
  separate processes (exactly how real hooks write) and asserts the live tail
  picks the events up — the "is it updating?" question is CI-proven forever.

## 0.4.2 — 2026-07-17

- **Liveness heartbeat** in the dashboard hint line: "live · last event 12s ago",
  or "listening for doc reads (injected context never shows here)" when nothing
  has arrived yet — answers "is it stale or is nothing happening?" at a glance.

## 0.4.1 — 2026-07-17

- Launcher pane messages now explain exit causes: SIGTERM/SIGINT (e.g. an external
  `kill`) reads "terminated from outside — not a crash" instead of a bare status
  code; real crashes say "crashed". Ends the status-143 confusion.

## 0.4.0 — 2026-07-17

- **External ingestion adapter**: `tt-log.py ingest '<event-json>'` — a stable,
  validated entry point so any tool (a Codex wrapper, a git hook, an editor
  plugin) can append telemetry to the same history. Missing ts/session stamped,
  invalid events dropped silently. Completes the plugin side of multi-tool support.

## 0.3.7 — 2026-07-17

- `/tt watch` confirmation line now prints the running plugin version
  ("trigger-tree v0.3.7 watcher opened …") so a stale session cache is instantly
  visible. FAQ entry added for the flash-and-disappear symptom (stale pre-v0.3.3
  cache → `/reload-plugins`).

## 0.3.6 — 2026-07-17

- **Positioning, research-backed**: README and site now state the validated gap —
  agent observability tools measure tokens/traces, none measure per-task doc reads;
  Anthropic's guidance says to prune CLAUDE.md but nothing validates the pruning;
  the Fallow analogy (unused code → unused docs). Added a who-is-it-for table and
  an honest Limitations section (official-plugin convention).

## 0.3.5 — 2026-07-17

- **Branding: lowercase everywhere.** The plugin now presents itself as
  `trigger-tree` across README, website, dashboard banner, SKILL, report and
  manifests — matching the naming convention of official Claude Code plugins
  (`commit-commands`, `security-guidance`, …). The `/tt` command is unchanged.

## 0.3.4 — 2026-07-17

- **Stability: layered, crash-proof config resolution** in all scripts (project
  override → plugin default → hardcoded; broken regexes skipped). Fixes the
  instant-crash of `/tt watch` in projects with a partial `.trigger-tree/config.sh`.
- **Multi-session safe splits**: the iTerm2 split now targets the exact session
  that invoked it (via `ITERM_SESSION_ID`) — two Claude sessions in different
  projects each get their own split, never the frontmost window by accident.
- **Discovery-structure awareness**: folders without an entry point are flagged
  ("no index file") and `/tt suggestions` proposes adding one; `_template.md`-style
  files are auto-classified as intentional archive; nested `CLAUDE.md`/
  `CLAUDE.local.md` files count as always-loaded (they inject on demand and are
  invisible to read-telemetry — per official memory docs).
- **README/site**: layman-first hero, "Why measure documentation?" and a sourced
  "Structuring your docs for discovery" guide; site now has six feature cards and
  a "Why this matters" section.

## 0.3.3 — 2026-07-17

- **Fix: iTerm2 split closed instantly.** iTerm2's AppleScript `command` parameter
  is exec-style (no shell), so the compound `cd … && …` command died on launch.
  The split now runs a generated launcher script (shebang + shell), which also
  keeps the pane open with the error message if the watcher ever exits non-zero.

## 0.3.2 — 2026-07-17

- **Dashboard visual parity with the website demo**: three-tier heat palette
  (green → amber → red), clean folder lines (untouched counters only appear when
  files are collapsed), "just now" ticker, dim `q quit` hint line.
- **Documentation health grade**: deterministic A–F score (coverage, router gaps,
  hunting ratio) in stats, `/tt status`, `/tt insights` and as hero card in the
  HTML report — one number a product owner can track sprint over sprint.

## 0.3.1 — 2026-07-17

- `/tt watch` on macOS now stays in the terminal you called it from: iTerm2 users
  get a split pane in the current window (detected via `TERM_PROGRAM`), with a
  new-window fallback; Terminal.app remains the fallback for everything else.

## 0.3.0 — 2026-07-17

- **Windows support**: posix path normalization, utf-8 everywhere, ANSI console
  enable + msvcrt keys in the dashboard, `wt.exe`/`start` launcher branch,
  `python3||python` fallbacks. CI test matrix now runs ubuntu + macos + windows.
- **Folder heat & cold map**: per-folder coverage and read volume in stats and the
  HTML report.
- **Router-gap detection**: untouched files are cross-referenced against all docs —
  "untouched and unreferenced" pinpoints where the router is blind.
- **`/tt suggestions`**: max 5 prioritized, evidence-backed router fixes, applied
  only after confirmation.
- **README overhaul** (hero, how-it-works with hook transparency, FAQ, platform
  matrix) and a **website** at hedde.github.io/trigger_tree — an interactive
  recreation of the live dashboard, with a few easter eggs for the curious.

## 0.2.1 — 2026-07-17

- Rename plugin id `tt` → `trigger-tree` for the plugin directory (unique, descriptive
  name). The `/tt` command is unchanged — it comes from the root skill's `name` field.
- GitHub Pages docs site: https://hedde.github.io/trigger_tree/

## 0.2.0 — 2026-07-17

- **Skill-tool telemetry**: PostToolUse hook on `Skill` logs skill invocations; an
  invoked skill's SKILL.md counts as touched, shrinking the `always_loaded` blind spot.
- **Portability**: logger and statusline rewritten in pure python3 (jq and BSD `date`
  dependencies dropped); `/tt watch` opens a tmux split, macOS Terminal, or
  gnome-terminal/konsole/xterm.
- **Prompt privacy**: `TT_LOG_PROMPTS=truncate|hash|off` — fingerprints keep working
  in all modes.
- **Log rotation**: history.jsonl rotates to timestamped archives beyond
  `TT_ROTATE_BYTES` (default 5 MB); aggregator and watcher read all archives.
- **Trend + annotations**: daily/weekly reads-scans buckets with hunting ratio;
  `/tt note <text>` marks router changes on the timeline so their effect is visible.
- **Task clusters**: fingerprints grouped by Jaccard similarity (≥ 0.6) instead of
  exact-set matching.
- **`/tt setup`**: idempotent project wiring (gitignore, statusline copy +
  registration, optional config override).
- **CI**: unit + smoke tests with an 80% coverage gate, shellcheck,
  `claude plugin validate`. Measured coverage is published as a live badge
  (shields endpoint JSON on the `badges` branch — no external coverage service).
- **Community files**: CONTRIBUTING, code of conduct, security policy, issue/PR
  templates, README badges.

## 0.1.0 — 2026-07-17

Initial release.

- Telemetry hooks (SessionStart, UserPromptSubmit, PostToolUse on Read|Glob|Grep) →
  `.trigger-tree/history.jsonl`, shell-side, zero model tokens.
- `/tt` root skill with subcommands: `status`, `watch [demo|replay]`, `insights`, `help`.
- Live ASCII pulse dashboard (`tt-watch.py`): heat-colored doc tree, white flash +
  upward ripple per read, hunting ticker, subagent attribution.
- Deterministic aggregator (`tt-stats.py`): per-file read counts, task fingerprints,
  co-read pairs, hunting, untouched paths with a maturity model
  (cold-start → warming → mature).
- Self-contained HTML report (`tt-report.py`), published via Artifact from `/tt insights`.
- Statusline script with age-based pulse dot (ships with the plugin; registered per
  project).
