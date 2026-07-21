# Security Policy

## Data handling

trigger-tree is local-only by design: telemetry is written to
`$PROJECT/.trigger-tree/` on your machine and never leaves it. No network calls, no
external services, no dependencies. Before setup, prompt markers use a short SHA-1
fingerprint and contain no prompt text. The recommended `/tt setup` flow stores a
recognizable 200-character local preview by default and explains that choice. Projects
can instead choose `TT_LOG_PROMPTS=hash` or `TT_LOG_PROMPTS=off` during setup.

## Supported versions

The latest release on `main` receives fixes. Older versions: please upgrade.

## Reporting a vulnerability

Please do **not** open a public issue for security problems. Email
**me@heddevanderheide.nl** with a description and reproduction steps. You will
get a response within a few days; fixes are credited unless you prefer otherwise.
