# trigger-tree repository guidance

Keep this file as a router. Read only the references needed for the task.

| Task | Start here |
|---|---|
| Product behavior or terminology | `docs/README.md`, then `docs/glossary.md` |
| Telemetry, heat, health, or limitations | `docs/heat-model.md` |
| TUI or HTML report | `docs/dashboard.md` |
| Hook/config changes | `docs/configuration.md` and `docs/platform-support.md` |
| Privacy-sensitive changes | `docs/privacy.md` and `PRIVACY.md` |
| Tests, CI, or release work | `docs/development.md` and `CONTRIBUTING.md` |
| Documentation structure | `docs/structuring-docs.md` |

Before shipping, run the full checks in `docs/development.md`. Preserve stdlib-only runtime code, local-only telemetry, explicit uncertainty, and 100% test coverage.
