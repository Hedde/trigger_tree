# Development and release

Use a virtual environment:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-test.txt -r requirements-dev.txt
.venv/bin/black --check scripts tests .github/scripts
.venv/bin/ruff check scripts tests .github/scripts
.venv/bin/python -m coverage run -m pytest tests -q
.venv/bin/python -m coverage report --fail-under=100
shellcheck scripts/tt-open.sh scripts/tt-shell-capture.sh
npx claude plugin validate .
python3 .github/scripts/plugin_install_smoke.py
```

CI also audits workflow syntax/security and release-tag integrity. On every version tag it publishes the GitHub release notes from the changelog and the `trigger-tree` package to PyPI via trusted publishing (OIDC; the publisher binding is configured on pypi.org, no stored secrets). Versions must agree in all manifests and the changelog. See [CONTRIBUTING.md](../CONTRIBUTING.md).
