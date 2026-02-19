# Scripts

This directory contains maintained operational and development scripts.
Run all scripts from the repository root.

## CI and Security

- `scripts/semgrep-isolated.sh`
  - Wrapper used by GitHub Actions to run Semgrep in an isolated environment.
- `scripts/ci-exact-simulation.sh`
  - Local simulation of CI checks.
- `scripts/ci-sync-validator.sh`
  - Verifies local CI simulation remains aligned with workflow definitions.
- `scripts/pre-commit-ci-validation.sh`
  - Runs pre-commit CI validations before commit/push.
- `scripts/quality-check.sh`
  - Local lint/type/test/security quality checks.

## Release and Go-Live

- `scripts/go-live-gate.sh`
  - End-to-end release gate script.
- `scripts/test-http-transport.sh`
  - Live HTTP transport test.
- `scripts/test-auth-http-transport.sh`
  - Live HTTP auth-boundary transport test.
- `scripts/bump_version.py`
  - Version bump helper.

## Content Maintenance

- `scripts/update-static-fallback.py`
  - Refreshes static fallback lists from upstream content.

## Developer Environment

- `scripts/dev-setup.sh`
  - Full development setup.
- `scripts/dev-quick-setup.sh`
  - Faster setup path.
- `scripts/dev-reset.sh`
  - Resets local development environment.
- `scripts/dev-test.sh`
  - Development test runner.
- `scripts/dev-test-focused.sh`
  - Focused test runner for selected scopes.
- `scripts/clean.sh`
  - Cleans build/test/cache artifacts.

## Optional Hardening

- `scripts/install-ironclad-protection.sh`
  - Optional local git protection/hardening utility.

## Notes

- Scripts removed in cleanup were deprecated, stale, or referenced non-existent paths.
- If you add a new script, add it to this README and reference it from the workflow/docs that depend on it.
