# Security Policy

## Data handling

trigger-tree is local-only by design: telemetry is written to
`$PROJECT/.trigger-tree/` on your machine and never leaves it. No network calls, no
external services, no dependencies. Prompt logging is configurable
(`TT_LOG_PROMPTS=truncate|hash|off`) for teams that don't want prompt text on disk.

## Supported versions

The latest release on `main` receives fixes. Older versions: please upgrade.

## Reporting a vulnerability

Please do **not** open a public issue for security problems. Email
**me@heddevanderheide.nl** with a description and reproduction steps. You will
get a response within a few days; fixes are credited unless you prefer otherwise.
