# Development and release

Use a virtual environment:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-test.txt -r requirements-dev.txt
.venv/bin/black --check scripts tests .github/scripts docs/assets
.venv/bin/ruff check scripts tests .github/scripts docs/assets
.venv/bin/python -m coverage run -m pytest tests -q
.venv/bin/python -m coverage report --fail-under=100
shellcheck scripts/tt-open.sh scripts/tt-shell-capture.sh
npx claude plugin validate .
python3 .github/scripts/plugin_install_smoke.py
```

CI also audits workflow syntax/security and release-tag integrity. On every version tag it
publishes the GitHub release notes from the changelog, the `trigger-tree` package to PyPI
via trusted publishing (OIDC; the publisher binding is configured on pypi.org, no stored
secrets), and the Codex upload archive as a release asset. Versions must agree in all
manifests and the changelog.

A release is not done until the Codex archive is attached and valid. CI builds it with
`.github/scripts/build_codex_zip.py`, then `.github/scripts/verify_codex_zip.py` rejects
the release if the archive is corrupt, is missing a runtime file, leaks the
repository-only `codex-skills/` tree, disagrees with the tag version, or declares a
`skills` root that holds no `SKILL.md` inside the archive. Build and verify it locally
before tagging if you want to catch that early:

```bash
python3 .github/scripts/build_codex_zip.py
python3 .github/scripts/verify_codex_zip.py dist-submissions/trigger-tree-codex.zip vX.Y.Z
```

Uploading that archive to the Codex portal remains a manual web step; the release asset
is the artifact to upload. See [CONTRIBUTING.md](../CONTRIBUTING.md).
