# Release Process

This document describes the release process for the AI Governance MCP Server.

## Overview

The project uses semantic versioning and automated release workflows with manual approval gates for PyPI publishing.

## Version Scheme

We follow [Semantic Versioning (SemVer)](https://semver.org/):

- **Major** (`X.0.0`): Breaking changes, incompatible API changes
- **Minor** (`0.X.0`): New features, backward compatible
- **Patch** (`0.0.X`): Bug fixes, backward compatible
- **Prerelease**: `1.0.0-alpha.1`, `1.0.0-beta.1`, `1.0.0-rc.1`

## Release Types

### Production Releases

1. **Patch Release** (bug fixes)
   ```bash
   python scripts/bump_version.py patch
   ```

2. **Minor Release** (new features)
   ```bash
   python scripts/bump_version.py minor
   ```

3. **Major Release** (breaking changes)
   ```bash
   python scripts/bump_version.py major
   ```

### Prerelease Versions

1. **Alpha Release** (early development)
   ```bash
   python scripts/bump_version.py alpha
   ```

2. **Beta Release** (feature complete, testing)
   ```bash
   python scripts/bump_version.py beta
   ```

3. **Release Candidate** (final testing)
   ```bash
   python scripts/bump_version.py rc
   ```

4. **Promote to Release** (remove prerelease suffix)
   ```bash
   python scripts/bump_version.py release
   ```

## Release Process

### 1. Pre-Release Validation

Before creating any release, ensure all quality gates pass:

```bash
# Run full stability validation
source .venv/bin/activate
python tests/run_stability_validation.py

# Verify type checking passes
.venv/bin/python -m mypy src/

# Run linting and formatting
.venv/bin/python -m ruff check
.venv/bin/python -m ruff format --check

# Run tests
.venv/bin/python -m pytest tests/ -v

# Test console script
finos-mcp --help
```

**All tests must pass before proceeding.**

### 2. Version Bumping

Use the provided script to bump the version:

```bash
# For patch release (bug fixes)
python scripts/bump_version.py patch

# For minor release (new features)
python scripts/bump_version.py minor

# For major release (breaking changes)
python scripts/bump_version.py major
```

This will:
- Update `pyproject.toml`
- Update `src/finos_mcp/_version.py`
- Show you the commands to run next

### 3. Commit and Tag

After version bump, commit and create a tag:

```bash
git add .
git commit -m "chore: bump version to X.Y.Z"
git tag vX.Y.Z
git push origin main --tags
```

### 4. Automated Release Workflow

Pushing a tag triggers the automated release workflow (`.github/workflows/release.yml`):

1. **Validation**: Runs full test suite and security checks
2. **Build**: Creates wheel and source distributions
3. **Provenance**: Generates SLSA provenance metadata
4. **GitHub Release**: Creates release with changelog and artifacts
5. **PyPI Publishing**: Publishes to Test PyPI first, then PyPI (requires manual approval)

### 5. Manual Approval for PyPI

The PyPI publishing step requires manual approval through GitHub environments:

1. Go to the Actions tab in GitHub
2. Find the release workflow run
3. Review the build artifacts and validation results
4. Approve the `publish-pypi` job when ready

### 6. Post-Release Verification

After release, verify:

1. **GitHub Release**: Check release page has correct artifacts
2. **PyPI Package**: Verify package is available
3. **Installation Test**: Test fresh installation
   ```bash
   pip install git+https://github.com/hugo-calderon/finos-mcp-server.git@vX.Y.Z
   finos-mcp --help
   ```

## Conventional Commits

We enforce [Conventional Commits](https://www.conventionalcommits.org/) for automatic changelog generation:

### Commit Types

- **feat**: New features (minor version bump)
- **fix**: Bug fixes (patch version bump)
- **docs**: Documentation changes
- **style**: Code style changes (no logic change)
- **refactor**: Code refactoring
- **test**: Test changes
- **chore**: Build/tooling changes
- **perf**: Performance improvements
- **ci**: CI configuration changes
- **build**: Build system changes
- **revert**: Revert previous commit

### Commit Format

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

### Examples

```bash
feat: add support for custom document filters
fix(parser): handle malformed YAML gracefully
docs: update installation instructions
chore(deps): update dependencies to latest versions
```

### Breaking Changes

For breaking changes, add `!` after type/scope:

```bash
feat!: remove deprecated search API
fix(parser)!: change return type for parse_frontmatter
```

Or use footer:

```bash
feat: add new configuration system

BREAKING CHANGE: Configuration file format changed from YAML to TOML
```

## Hotfix Process

For critical bugs in production:

1. Create hotfix branch from main
2. Fix the issue
3. Run validation tests
4. Bump patch version
5. Create PR to main
6. After merge, tag and release

```bash
git checkout -b hotfix/critical-bug-fix main
# Make fixes
python scripts/bump_version.py patch
git add .
git commit -m "fix: critical security vulnerability"
git push origin hotfix/critical-bug-fix
# Create PR, merge, then tag
git checkout main
git pull origin main
git tag vX.Y.Z
git push origin main --tags
```

## Release Checklist

### Pre-Release

- [ ] All tests passing locally
- [ ] All CI checks passing
- [ ] Documentation updated
- [ ] CHANGELOG reviewed (auto-generated)
- [ ] Version bumped appropriately
- [ ] Security scans clean

### Release

- [ ] Tag created and pushed
- [ ] GitHub Actions workflow completed
- [ ] GitHub release created with artifacts
- [ ] Test PyPI package verified
- [ ] Production PyPI package published
- [ ] Installation test completed

### Post-Release

- [ ] Release announced (if significant)
- [ ] Issues closed that were resolved
- [ ] Release artifacts validated
- [ ] Post-release issue created (automated)

## Rollback Process

If a release has critical issues:

### GitHub Release

1. Mark release as pre-release in GitHub UI
2. Update release notes with warning

### PyPI Package

PyPI doesn't support deleting packages, but you can:

1. Yank the release: `twine yank <package> <version>`
2. Release a hotfix version immediately

### Emergency Response

For security issues:

1. Immediately yank PyPI release
2. Create security advisory in GitHub
3. Prepare hotfix release ASAP
4. Coordinate disclosure with security team

## Troubleshooting

### Release Workflow Fails

1. Check GitHub Actions logs
2. Verify all secrets are configured:
   - `PYPI_API_TOKEN`
   - `TEST_PYPI_API_TOKEN`
3. Ensure tag format is correct (`vX.Y.Z`)

### PyPI Publishing Issues

1. Check API tokens are valid
2. Verify package name is available
3. Ensure wheel builds correctly locally:
   ```bash
   python -m build
   twine check dist/*
   ```

### Version Conflicts

1. Check current version: `python scripts/bump_version.py --current`
2. Verify tags match versions: `git tag -l`
3. Ensure no duplicate tags exist

## Automation Details

The release process is highly automated but includes manual approval gates for security:

- **Automated**: Testing, building, GitHub releases, Test PyPI
- **Manual Approval**: Production PyPI publishing
- **SLSA Provenance**: Supply chain security metadata
- **Security Scans**: Integrated into release pipeline

This ensures both development velocity and production safety.
