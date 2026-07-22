# Security Policy

## Data handling

trigger-tree is local-only by design: telemetry is written to
`$PROJECT/.trigger-tree/` on your machine and never leaves it. No network calls, no
external services, no dependencies. Before and after setup, the default stores a
recognizable 200-character preview in the project's gitignored telemetry. Interactive
setup explains and asks for that choice. Projects can instead choose
`TT_LOG_PROMPTS=hash` (no prompt text) or `TT_LOG_PROMPTS=off` during setup.

## Supported versions

The latest release on `main` receives fixes. Older versions: please upgrade.

## Reporting a vulnerability

Please do **not** open a public issue for security problems. Email
**me@heddevanderheide.nl** with a description and reproduction steps. You will
get a response within a few days; fixes are credited unless you prefer otherwise.
