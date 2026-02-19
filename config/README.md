# ⚙️ Configuration Management

This directory contains all configuration files organized by purpose, providing a centralized and maintainable approach to project configuration.

## 📁 Directory Structure

```
config/
├── security/          # 🔒 Security configurations
├── quality/           # ✨ Code quality configurations
├── ci/               # 🔄 CI/CD configurations
└── dependencies/     # 📦 Dependency management
```

## 🔒 Security Configuration (`security/`)

Contains all security-related configuration files:

- **`bandit.yml`** - Security scanning configuration for Python code
- **`semgrep.yml`** - Security rules for static analysis
- **`safety.json`** - Known vulnerability database configuration

## ✨ Quality Configuration (`quality/`)

Code quality and linting configurations:

- **`pylint.cfg`** - Python linting rules and standards
- **`mypy.ini`** - Static type checking configuration
- **`ruff.toml`** - Fast Python linting and formatting
- **`coverage.ini`** - Test coverage reporting configuration

## 🔄 CI/CD Configuration (`ci/`)

Continuous integration and deployment configurations:

- **`pre-commit-config.yaml`** - Git pre-commit hooks
- **`github-actions.yml`** - GitHub Actions workflow templates
- **`docker/`** - Docker configurations for various environments

## 📦 Dependency Management (`dependencies/`)

Dependency and package management files:

- **`requirements.lock`** - Locked dependency versions for reproducible builds
- **`requirements-dev.txt`** - Development-specific dependencies
- **`requirements-test.txt`** - Testing framework dependencies

## 🛠️ Usage

### Local Development
Most configurations are automatically discovered by their respective tools when placed in these standard locations.

### CI/CD Integration
GitHub Actions and other CI systems reference these configurations using relative paths:

```yaml
# Example: Reference security config in GitHub Actions
- name: Security Scan
  run: bandit -c config/security/bandit.yml -r src/
```

### Customization
To customize configurations for your environment:

1. Copy the relevant configuration file
2. Modify settings as needed
3. Update tool invocations to reference your custom config

## 📋 Configuration Standards

All configuration files in this directory follow these standards:

- ✅ **Version controlled** - All configs are tracked in git
- ✅ **Environment agnostic** - No hardcoded paths or secrets
- ✅ **Well documented** - Include comments explaining settings
- ✅ **Consistent naming** - Follow established naming conventions
- ✅ **Validation ready** - Configurations validated in CI/CD

## 🔧 Maintenance

When adding new configurations:

1. Place in the appropriate subdirectory based on purpose
2. Add documentation explaining the configuration
3. Update this README with the new file
4. Test the configuration in CI/CD pipeline
5. Update any scripts that reference the old location

---

> **Note**: Moving configurations to this centralized location improves maintainability and makes the project structure more professional and enterprise-ready.
