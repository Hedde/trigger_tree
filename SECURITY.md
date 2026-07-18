# Security Policy

## Data handling

trigger-tree is local-only by design: telemetry is written to
`$PROJECT/.trigger-tree/` on your machine and never leaves it. No network calls, no
external services, no dependencies. Prompt text is not stored by default: task
markers use a short SHA-1 hash. Projects can choose `TT_LOG_PROMPTS=off` or
explicitly opt in to `truncate`.

## Supported versions

The latest release on `main` receives fixes. Older versions: please upgrade.

## Reporting a vulnerability

Please do **not** open a public issue for security problems. Email
**me@heddevanderheide.nl** with a description and reproduction steps. You will
get a response within a few days; fixes are credited unless you prefer otherwise.
