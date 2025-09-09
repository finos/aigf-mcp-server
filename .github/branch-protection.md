# Branch Protection Configuration

This document describes the recommended branch protection rules for the FINOS MCP Server repository.

## Required Status Checks

The following CI jobs must pass before merging to `main`:

### Core Quality Gates
- **Code Quality Gates** (`quality-gates`)
  - Ruff linting and formatting
  - MyPy type checking
  - Bandit security scanning
  - Test coverage ≥70%

### Cross-Platform Testing
- **Test Matrix** (`test-matrix`)
  - Python 3.9, 3.10, 3.11, 3.12, 3.13 on Ubuntu
  - Python 3.13 on macOS and Windows
  - Stability validation for all versions
  - Console script functionality verification

### Security and Build
- **Security Scanning** (`security-scan`)
  - pip-audit dependency vulnerability scanning
  - Secret detection with detect-secrets

- **Build Test** (`build-test`)
  - Package build verification
  - Installation testing
  - Artifact validation

- **Integration Tests** (`integration-test`)
  - End-to-end functionality testing
  - MCP protocol compliance verification

- **CI Success** (`ci-success`)
  - Final validation that all jobs passed

## GitHub Repository Settings

### Branch Protection Rules for `main`

```json
{
  "required_status_checks": {
    "strict": true,
    "contexts": [
      "Code Quality Gates",
      "Test Python 3.9",
      "Test Python 3.10",
      "Test Python 3.11",
      "Test Python 3.12",
      "Test Python 3.13",
      "Test Python 3.13 (macos-latest)",
      "Test Python 3.13 (windows-latest)",
      "Security Scanning",
      "Build and Package Test",
      "Integration Tests",
      "CI Success"
    ]
  },
  "enforce_admins": false,
  "required_pull_request_reviews": {
    "required_approving_review_count": 1,
    "dismiss_stale_reviews": true,
    "require_code_owner_reviews": true,
    "require_last_push_approval": false
  },
  "required_linear_history": false,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_conversation_resolution": true
}
```

### Manual Configuration Steps

1. **Navigate to Repository Settings**
   - Go to your GitHub repository
   - Click "Settings" → "Branches"

2. **Add Branch Protection Rule**
   - Click "Add rule"
   - Branch name pattern: `main`

3. **Configure Protection Settings**
   - ✅ Require pull request reviews before merging
     - Required approving reviews: 1
     - ✅ Dismiss stale pull request approvals when new commits are pushed
     - ✅ Require review from code owners

   - ✅ Require status checks to pass before merging
     - ✅ Require branches to be up to date before merging
     - Add all status checks listed above

   - ✅ Require conversation resolution before merging
   - ❌ Require signed commits (optional for open source)
   - ❌ Require linear history (allows merge commits)
   - ❌ Allow force pushes
   - ❌ Allow deletions

4. **Additional Security Settings**
   - Enable Dependabot alerts
   - Enable secret scanning
   - Enable code scanning (CodeQL)

## Development Workflow

### For Contributors

1. **Create Feature Branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make Changes Following Type-First Development**
   - Design types and protocols first
   - Run local validation:
     ```bash
     # Type checking
     mypy src/ --strict

     # Code quality
     ruff check .
     ruff format --check .

     # Security
     bandit -r src/

     # Tests
     pytest --cov=finos_mcp --cov-fail-under=70
     ```

3. **Create Pull Request**
   - All CI checks must pass
   - At least 1 approving review required
   - All conversations must be resolved

4. **Merge to Main**
   - Use "Squash and merge" for clean history
   - Delete feature branch after merge

### For Maintainers

- **Pre-commit Hooks**: Ensure `.pre-commit-config.yaml` is configured
- **Code Owners**: Configure `.github/CODEOWNERS` for automatic review requests
- **Release Process**: Use semantic versioning and conventional commits

## Troubleshooting CI Failures

### Common Issues

1. **Type Checking Failures**
   ```bash
   # Run locally to debug
   mypy src/ --show-error-codes --strict
   ```

2. **Test Coverage Below 70%**
   ```bash
   # Check coverage report
   pytest --cov=finos_mcp --cov-report=html
   open htmlcov/index.html
   ```

3. **Security Scan Issues**
   ```bash
   # Check for secrets
   detect-secrets scan --all-files

   # Check dependencies
   pip-audit --desc
   ```

4. **Matrix Test Failures**
   - Usually Python version compatibility issues
   - Check deprecation warnings and API changes
   - Use `python -m pytest -W error::DeprecationWarning` to catch early

## Success Criteria

✅ **Step 17 Complete When:**
- All CI jobs pass consistently
- Branch protection rules prevent broken code merges
- Matrix testing covers Python 3.9-3.13
- Security scanning catches vulnerabilities
- Coverage threshold enforced at 70%
- Integration tests validate end-to-end functionality

The CI pipeline ensures code quality, security, and reliability for the FINOS MCP Server project.
