# Scripts

This directory contains maintained operational and development scripts.
Run all scripts from the repository root.

## CI and Security

- `scripts/ci-local.sh`
  - Local CI-equivalent runner for lint/type/test/security checks.
- `scripts/semgrep-isolated.sh`
  - Wrapper used by GitHub Actions to run Semgrep in an isolated environment.
- `scripts/ci-exact-simulation.sh`
  - Local simulation helper for deep CI troubleshooting.
- `scripts/ci-sync-validator.sh`
  - Verifies local CI simulation remains aligned with workflow definitions.

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

## Notes

- Additional personal developer convenience scripts can be maintained locally and should not be committed.
- If you add a new script, add it to this README and reference it from the workflow/docs that depend on it.
