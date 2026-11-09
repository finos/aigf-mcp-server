# Scripts

This directory contains maintained operational and development scripts.
Run all scripts from the repository root.

Every tracked file here has an entry below, and
`tests/unit/test_scripts_inventory.py` fails if one is missing, or if this
file names a path under `scripts/` that git does not track. An entry marked
*manual* is run by a person: no workflow, pre-commit hook or other script
invokes it.

## CI and Security

- `scripts/ci-local.sh`
  - *Manual.* The full local gate, in CI order: bandit, semgrep, pylint, ruff, mypy,
    pytest with coverage, pip-audit, pre-commit, then the functional gate (the
    live stdio and HTTP auth tests). It stops if the pre-push hook is not
    installed. This is the script
    `docs/development.md` tells contributors to run. Override the interpreter with
    `PYTHON_BIN=...`.
- `scripts/pip-audit-scan.sh`
  - The single entry point for the dependency audit. Suppressions are declared
    once in `[tool.finos.pip-audit]`; never pass `--ignore-vuln` at a call site.
- `scripts/pip_audit_policy.py`
  - Resolves that suppression policy for the scan script.
- `scripts/semgrep-isolated.sh`
  - Wrapper used by GitHub Actions to run Semgrep in an isolated environment.
- `scripts/ci-exact-simulation.sh`
  - *Manual.* Local simulation of CI checks. `tests/unit/test_ci_config_drift.py`
    holds it to the same tool invocations as the workflows.
- `scripts/quality-check.sh`
  - *Manual.* Local lint/type/test/security quality checks.
- `scripts/project-python.sh`
  - Resolves the interpreter every gate runs on. `language: system`
    pre-commit hooks and the wrapper scripts delegate to it; workflows reach
    it through those.
- `scripts/project_environment.py`
  - Run by `project-python.sh`: checks that the resolved interpreter holds the
    dependencies `pyproject.toml` declares.
- `scripts/coverage-summary.sh`
  - The one place a call site reads the coverage percentage from a coverage.py
    JSON report. Run by the workflows and `ci-exact-simulation.sh`.
- `scripts/check-codeowners.sh`
  - Asks GitHub whether it can resolve `.github/CODEOWNERS`. Run by the
    Security Analysis workflow and by go-live Gate 10.
- `scripts/scan-blocked-filenames.sh`
  - Body of the `block-dev-only-files` pre-commit hook.
- `scripts/scan-blocked-references.sh`
  - Body of the `scan-dev-only-references` pre-commit hook.

## Release and Go-Live

- `scripts/go-live-gate.sh`
  - End-to-end release gate script. Run by the Go-Live Gate workflow weekly,
    on demand, and on pull requests that change `scripts/` or `SECURITY.md`;
    run it by hand on release day too.
- `scripts/check-release-tag.py`
  - Run twice by the Release workflow: on the pushed tag's name before the
    gates, and with `--dist dist` on the built files before they are uploaded.
    Refuses a tag the build cannot parse and files named for another version.
    With `--github-output FILE` it also writes whether the version is a
    prerelease, which the workflow uses to mark the release.
- `scripts/dev-only-paths.sh`
  - The one definition of a development-only path. Sourced by
    `go-live-gate.sh` and `scan-published-refs.sh`.
- `scripts/scan-published-refs.sh`
  - Body of go-live Gate 9: refuses to go live while a ref on the remote
    publishes development-only files.
- `scripts/check-security-policy.sh`
  - Body of go-live Gate 11: asks GitHub whether the reporting form is
    available (a public repository with private vulnerability reporting
    enabled) and refuses a `SECURITY.md` that says the other.
    `GO_LIVE_VISIBILITY=public` checks the linked form without asking.
- `scripts/security_policy_route.py`
  - Run by `check-security-policy.sh`: the one definition of the two forms
    `SECURITY.md` can take. `tests/unit/test_security_policy.py` imports it.
- `scripts/test-http-transport.sh`
  - Live HTTP transport test, run by `go-live-gate.sh`.
- `scripts/test-auth-http-transport.sh`
  - Live HTTP auth-boundary transport test, run by `go-live-gate.sh`.

There is no version-bump script. The version is derived from the git tag by
setuptools-scm (`dynamic = ["version"]` in `pyproject.toml`), so no file holds
a version string to edit.

## Content Maintenance

- `scripts/update-static-fallback.py`
  - *Manual.* Writes `src/finos_mcp/content/static_catalog.py`, the listing the
    server serves when GitHub cannot be asked, from the live listing. The
    Validate Static Fallback Sync workflow tells you when to run it.

## Documentation

- `scripts/generate-tool-table.py`
  - *Manual.* Writes the tool table in `README.md` from the tools the server
    publishes. `tests/unit/test_generated_tool_table.py` fails when the table
    is stale and tells you to run it.

## Developer Environment

All *manual*.

- `scripts/dev-setup.sh`
  - Full development setup.
- `scripts/dev-quick-setup.sh`
  - Faster setup path.
- `scripts/dev-reset.sh`
  - Resets local development environment.
- `scripts/dev-test.sh`
  - Development test runner.
- `scripts/clean.sh`
  - Cleans build/test/cache artifacts.
- `scripts/run-local-with-token.sh`
  - Runs a command with a GitHub token exported, raising the API limit from
    60 to 5000 requests/hour. Stores no credential: it uses
    `$FINOS_MCP_GITHUB_TOKEN` if set, otherwise `gh auth token`, and verifies
    the token against the API before running -- a revoked token returns 401
    where an unauthenticated request would have returned 200.

## Notes

- Scripts removed in cleanup were deprecated, stale, or referenced non-existent paths.
- If you add a new script, add it to this README and reference it from the workflow/docs that depend on it.
- A script nothing invokes and nobody runs is deleted, not listed (#75).
