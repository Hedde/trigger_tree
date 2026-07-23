# FAQ

## Where is my data?

In the project’s gitignored `.trigger-tree/history.jsonl` and rotated archives.

## Why are there zero docs at session start?

Injected guidance is loaded without a Read tool call. It is classified as always loaded rather than misrepresented as cold.

## A file is untouched but important

Untouched is a review signal. Check whether it is protected or missing from its folder router; the right fix may be a link, not deletion.

## The watch pane closes immediately

Reload plugins and confirm the running version. A current-version crash keeps the pane open with its error.

## Why is Claude telemetry empty on Windows?

Ensure `python3` resolves on `PATH`. Claude’s documented exec-form hooks do not provide an operating-system condition.

## Can prompt privacy change later?

Yes. Before a project runs setup only hashes are stored — hooks are user-wide,
and other repositories have not consented yet. Prefer no linkable hashes at all
before setup? Set `TT_LOG_PROMPTS='off'` in the user-wide
`~/.trigger-tree/config.sh`: it applies to every repository, and `tt doctor`
reports the effective mode with the layer that selected it. `/tt setup` asks per
project for `truncate` (a local, gitignored preview of at most 200 characters),
`hash`, or `off`; the project choice wins over the user default, and changing
the mode affects future events without rewriting history.

## How do I uninstall or publish the health badge?

`/tt uninstall` removes trigger-tree wiring but deliberately preserves local telemetry
and ignore entries for you to delete explicitly. `make badge-publish` publishes only the
aggregate local docs-health endpoint to an existing `badges` branch; it never publishes
paths or event history.

## Do Codex marketplace installs pin a version?

Yes: add the marketplace from a git ref and install from that snapshot —

```
codex plugin marketplace add Hedde/trigger_tree --ref vX.Y.Z
codex plugin add trigger-tree@trigger-tree
```

Without `--ref`, marketplace installs follow the repository default branch. The
GitHub Action (`uses: Hedde/trigger_tree@vX.Y.Z`) and
`pip install trigger-tree==X.Y.Z` pin the same way.

## Why does Codex record no events right after install or upgrade?

Codex runs plugin hooks only after you trust them, and it skips untrusted hooks
silently. Start the interactive TUI, review the **Hooks need review** prompt for
the four trigger-tree hooks, and choose **Trust all and continue**. Two things
are easy to miss: non-interactive `codex exec` runs never persist trust, and an
upgrade that changes a hook resets its trust, so the review comes back. `tt
doctor` reports the persisted trust state whenever a Codex install is present.
