# 🔧 FINOS AI Governance MCP Server - Automation Scripts

This directory contains automation scripts for developers working with the FINOS AI Governance MCP Server. These tools help with development setup, testing, quality validation, and project maintenance.

## 📁 Available Scripts

### 🛠️ **Development Workflow Scripts**

#### `dev-setup.sh` - Development Environment Setup
Complete development environment setup with all dependencies and tooling.

**Features:**
- Virtual environment creation and activation
- Dependency installation from lock files
- Pre-commit hooks configuration
- Development configuration setup
- Environment validation and testing

```bash
# Initial development setup
./scripts/dev-setup.sh
```

#### `ci-exact-simulation.sh` - Exact CI Simulation ⭐ **CRITICAL**
Run IDENTICAL commands to GitHub Actions CI to prevent validation mismatches.

**Features:**
- Exact 7-phase CI simulation matching GitHub Actions
- Bandit, Semgrep, Pylint, Ruff, MyPy, PyTest, pip-audit
- Same command arguments, thresholds, and failure conditions
- Guaranteed CI pass if local simulation passes

```bash
# MANDATORY before any commit
./scripts/ci-exact-simulation.sh
```

#### `ci-sync-validator.sh` - CI Synchronization Validator
Validates that local CI simulation remains synchronized with GitHub Actions.

**Features:**
- Detects command argument mismatches
- Validates all CI phases are present locally
- Checks failure thresholds alignment
- Prevents CI configuration drift

```bash
# Run after ANY GitHub Actions workflow changes
./scripts/ci-sync-validator.sh
```

#### `pre-commit-ci-validation.sh` - Pre-Commit Validation Hook
Comprehensive pre-commit validation ensuring code will pass CI.

**Features:**
- CI synchronization check
- Full CI simulation execution
- Sensitive information detection
- Commit message validation

```bash
# Run before any commit (or install as git hook)
./scripts/pre-commit-ci-validation.sh
```

#### `ci-local.sh` - Legacy Local CI Validation ⚠️ **DEPRECATED**
**DEPRECATED**: Use `ci-exact-simulation.sh` instead for guaranteed CI parity.

Run the same quality checks that run in CI locally.

**Features:**
- Code quality validation
- Security scanning
- Type checking
- Test execution with coverage

```bash
# DEPRECATED - Use ci-exact-simulation.sh instead
./scripts/ci-local.sh
```

#### `quality-check.sh` - Quality Validation
Comprehensive quality validation including linting, type checking, and security scanning.

**Features:**
- Ruff linting and formatting
- MyPy strict type checking
- Pylint code quality analysis (≥9.5 score)
- Bandit security scanning
- pip-audit vulnerability scanning

```bash
# Run all quality checks
./scripts/quality-check.sh

# Automatically fix issues
./scripts/quality-check.sh --fix
```

#### `clean.sh` - Development Environment Cleanup
Comprehensive cleanup of development artifacts and temporary files.

**Features:**
- Python cache file removal
- Build artifact cleanup
- Test artifact removal
- Log file cleanup
- Virtual environment removal (optional)

```bash
# Standard cleanup
./scripts/clean.sh

# Full cleanup including virtual environment
./scripts/clean.sh --all

# Dry run preview
./scripts/clean.sh --dry-run
```

### 🧪 **Testing Scripts**

- **`create_golden_files.py`** - Testing utilities for golden file baselines

## 🎯 Script Purposes

### Development Workflow Scripts
These scripts help developers get started quickly and maintain code quality:

- **Environment Setup**: Automated virtual environment creation, dependency installation
- **Quality Validation**: Linting, type checking, security scanning, test execution
- **Pre-commit Preparation**: Ensures code meets quality standards before committing

### CI/CD Integration Scripts
Scripts that integrate with continuous integration systems:

- **Quality Gates**: Automated quality checks for pull requests
- **Security Validation**: Vulnerability scanning and dependency auditing
- **Release Automation**: Version bumping, changelog generation, artifact creation

### Operational Scripts
Scripts for production deployment and maintenance:

- **Health Checks**: System health validation
- **Monitoring Setup**: Automated monitoring configuration
- **Backup Operations**: Data backup and recovery procedures

## 🛡️ Security Considerations

All scripts in this directory:

- ✅ **No hardcoded secrets** - Use environment variables for sensitive data
- ✅ **Input validation** - Validate all parameters and inputs
- ✅ **Error handling** - Proper error handling and logging
- ✅ **Safe defaults** - Conservative default settings
- ✅ **Audit logging** - Log all significant operations

## 🚨 CRITICAL LESSONS LEARNED: CI/Local Parity

### The pip-audit Phase Incident (September 2025)

**What Happened**: Local CI simulation script was missing Phase 7 (pip-audit dependency scanner) that exists in GitHub Actions CI. This caused dangerous validation mismatches:
- Local tests: PASSED (incomplete validation)
- GitHub Actions CI: FAILED (complete validation)

**Root Cause**: Missing pip-audit phase allowed vulnerable dependencies to pass local validation but fail in CI, creating development friction and potential security risks.

**Resolution**: Added complete 7-phase CI simulation that runs IDENTICAL commands to GitHub Actions.

### Critical Requirements Going Forward

**1. MANDATORY Pre-Commit Validation**
```bash
# REQUIRED before ANY commit
./scripts/ci-exact-simulation.sh
```

**2. CI Synchronization Monitoring**
```bash
# REQUIRED after ANY GitHub Actions workflow changes
./scripts/ci-sync-validator.sh
```

**3. Zero Tolerance for CI Mismatches**
- Local simulation MUST match CI exactly
- Command arguments must be identical
- All CI phases must be replicated locally
- Same failure thresholds and logic

### Preventive Measures Implemented

1. **Exact CI Simulation Script** - Runs identical commands to GitHub Actions
2. **CI Sync Validator** - Detects configuration drift between local and CI
3. **Pre-Commit Validation Hook** - Ensures code will pass CI before committing
4. **Comprehensive Documentation** - This incident and prevention strategies

**Key Takeaway**: Never trust local validation alone. Always simulate exact CI conditions to prevent deployment friction and maintain code quality standards.

## 🔧 Usage Guidelines

### Making Scripts Executable
```bash
chmod +x scripts/*.sh
```

### Running Scripts
Always run scripts from the project root directory:
```bash
# Correct
./scripts/setup.sh

# Incorrect
cd scripts && ./setup.sh
```

### Environment Variables
Scripts may require environment variables:
```bash
export FINOS_MCP_ENV=development
./scripts/setup.sh
```

### Script Dependencies
Some scripts require specific tools to be installed:
- **setup.sh**: Requires Python 3.9+, git
- **security-scan.sh**: Requires bandit, semgrep, safety
- **quality-check.sh**: Requires pylint, mypy, ruff

## 📋 Adding New Scripts

When adding new automation scripts:

1. **Follow naming conventions** - Use kebab-case (hyphen-separated)
2. **Add proper headers** - Include description, usage, and requirements
3. **Implement error handling** - Exit with proper status codes
4. **Add documentation** - Update this README with script description
5. **Test thoroughly** - Ensure scripts work in clean environments

### Script Template
```bash
#!/bin/bash
# Description: Brief description of what this script does
# Usage: ./scripts/script-name.sh [options]
# Requirements: List of required tools/dependencies

set -euo pipefail  # Exit on error, undefined vars, pipe failures

# Script implementation here
```

## 🧪 Testing Scripts

All scripts should be tested in:
- ✅ Clean development environments
- ✅ CI/CD pipelines
- ✅ Different operating systems (if applicable)
- ✅ Various Python versions (if applicable)

## 📞 Support

If you encounter issues with any scripts:

1. Check the script's built-in help: `./scripts/script-name.sh --help`
2. Verify all dependencies are installed
3. Check environment variables are properly set
4. Review the script's log output for error details
5. Create an issue if the problem persists

---

> **Note**: These automation scripts are designed to make development and operations as smooth as possible. They follow enterprise best practices for maintainability, security, and reliability.
