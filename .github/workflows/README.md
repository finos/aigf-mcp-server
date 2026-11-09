# GitHub Workflows

This directory contains the GitHub Actions workflows of the FINOS AI Governance MCP Server.

## Available Workflows

- **security-analysis.yml**: Comprehensive security and code quality analysis
- **release.yml**: Automated release management
- **dependabot-security-validation.yml**: Dependabot security validation
- **conventional-commits.yml**: Commit message validation
- **validate-static-fallback.yml**: Weekly check that the built-in catalog still matches upstream; opens an issue on drift
- **go-live-gate.yml**: Runs every automated gate in `scripts/go-live-gate.sh`

## Workflow Triggers

| Workflow | Runs on |
|---|---|
| `security-analysis.yml` | a push to `main` or `feature/*`, a pull request to `main`, Sundays at 02:00 UTC, manual dispatch |
| `conventional-commits.yml` | a pull request opened, edited or updated (it checks the title) |
| `dependabot-security-validation.yml` | a pull request to `main` opened, updated or reopened, manual dispatch |
| `go-live-gate.yml` | a pull request to `main` that changes `scripts/`, `SECURITY.md` or the workflow itself, Mondays at 07:00 UTC, manual dispatch |
| `validate-static-fallback.yml` | a push to `main` that changes `src/finos_mcp/content/static_catalog.py`, Mondays at 09:00 UTC, manual dispatch |
| `release.yml` | a pushed tag beginning with `v` only; it cannot be started by hand. See `docs/release-process.md` |
