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

Yes. `/tt setup truncate`, `hash`, or `off` changes future events and does not rewrite history.
