# Contributing to trigger-tree

Thanks for considering a contribution! This project is small on purpose — a zero-token
telemetry layer plus one `/tt` skill — so the bar for new code is "does it make the
measurement or the insights better without adding dependencies".

## Development setup

Always use a virtual environment — never install into your system python:

```bash
git clone https://github.com/Hedde/trigger_tree.git
cd trigger_tree
python3 -m venv .venv
.venv/bin/pip install pytest coverage
```

Run the plugin against a real project:

```bash
claude --plugin-dir /path/to/trigger_tree
```

## Tests

```bash
.venv/bin/python -m coverage run -m pytest tests -q
.venv/bin/python -m coverage report --fail-under=100
```

`tests/smoke.py` is the end-to-end pass over the fixture project; `tests/test_*.py`
are unit tests. New code needs tests — the CI coverage gate is a hard fail under 80%.

## Guidelines

- **Stdlib only.** The scripts run as hooks on every tool call; no pip dependencies.
- **Hooks must never disturb a session.** Loggers exit 0 on any failure, always.
- **Measure, don't force.** Discovery stays model-driven; this plugin observes it.
  Features that inject context or override routing belong in a discussion first.
- **Terminology.** Zero reads = *untouched*; only a mature measurement may say
  *dead-path candidate*.
- Conventional commits (`feat:`, `fix:`, `test:`, `docs:`, `chore:`).
- Keep `CHANGELOG.md` updated under an Unreleased/version heading.

## Pull requests

1. Fork, branch from `main`.
2. Add tests, run the suite locally (all three CI jobs: pytest+coverage, shellcheck
   on `scripts/tt-open.sh`, `claude plugin validate .`).
3. Open a PR with a short description of the behavior change and why.
