# Security Policy

## Data handling

trigger-tree is local-only by design: telemetry is written to
`$PROJECT/.trigger-tree/` on your machine and never leaves it. No network calls, no
external services, no dependencies. Installation can immediately store a recognizable
200-character prompt preview in the project's gitignored telemetry — but only
after that project's `/tt setup` chose it. Before setup the user-wide fallback is
`hash` (no prompt text), so installing the plugin never records prompt text in
repositories that have not consented. Projects choose `truncate`, `hash`, or
`off` during setup.

## Supported versions

The latest release on `main` receives fixes. Older versions: please upgrade.

## Reporting a vulnerability

Please do **not** open a public issue for security problems. Email
**me@heddevanderheide.nl** with a description and reproduction steps. You will
get a response within a few days; fixes are credited unless you prefer otherwise.
