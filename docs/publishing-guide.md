# 📦 Publishing Guide

Guide for publishing the FINOS AI Governance MCP Server to PyPI when ready for public release.

---

## 🚀 Pre-Publication Checklist

Before publishing to PyPI, ensure all requirements are met:

### ✅ **Code Quality**
- [ ] All tests pass (`pytest`)
- [ ] Code coverage ≥ 80%
- [ ] Security scans pass (Bandit, Semgrep)
- [ ] Type checking passes (MyPy)
- [ ] Linting passes (Ruff)

### ✅ **Documentation**
- [ ] README.md is complete and accurate
- [ ] API documentation is up to date
- [ ] Integration guide is comprehensive
- [ ] All examples work correctly

### ✅ **Package Configuration**
- [ ] `pyproject.toml` is properly configured
- [ ] Version is set correctly
- [ ] Dependencies are pinned appropriately
- [ ] Package metadata is complete

### ✅ **Legal & Compliance**
- [ ] License is properly configured (Apache-2.0)
- [ ] Copyright notices are in place
- [ ] FINOS attribution is correct
- [ ] No sensitive information in code

---

## 📋 Publishing Steps

### 1. **Prepare Release**

```bash
# Ensure clean working directory
git status

# Run full test suite
pytest --cov=finos_mcp --cov-report=term-missing

# Security scan
bandit -r src/

# Type check
mypy src/

# Lint code
ruff check . && ruff format --check .
```

### 2. **Build Package**

```bash
# Clean previous builds
rm -rf dist/ build/ *.egg-info/

# Build package
python -m build

# Verify package contents
python -m tarfile -l dist/*.tar.gz
python -m zipfile -l dist/*.whl
```

### 3. **Test Installation**

```bash
# Test in clean environment
python -m venv test-env
source test-env/bin/activate

# Install from wheel
pip install dist/*.whl

# Test basic functionality
python -c "import finos_mcp; print('✅ Import successful')"
finos-mcp --help
```

### 4. **Publish to Test PyPI** (Recommended)

```bash
# Install publishing tools
pip install twine

# Upload to Test PyPI
python -m twine upload --repository testpypi dist/*

# Test installation from Test PyPI
pip install --index-url https://test.pypi.org/simple/ finos-ai-governance-mcp-server
```

### 5. **Publish to PyPI**

```bash
# Final upload to PyPI
python -m twine upload dist/*
```

---

## 🔧 Configuration Updates

Once published to PyPI, update documentation:

### Update README.md

```bash
# Change installation instructions from:
git clone https://github.com/hugo-calderon/finos-mcp-server.git
cd finos-mcp-server
pip install -e .

# To:
pip install finos-ai-governance-mcp-server
```

### Update Integration Guides

Replace all source installation references with:

```json
{
  "mcpServers": {
    "finos-ai-governance": {
      "command": "finos-mcp",
      "args": ["stdio"],
      "env": {
        "FINOS_MCP_LOG_LEVEL": "INFO"
      }
    }
  }
}
```

---

## 🏷️ Version Management

### Semantic Versioning

Follow [SemVer](https://semver.org/) for version numbers:

- **MAJOR** (1.0.0): Breaking changes
- **MINOR** (0.1.0): New features, backward compatible
- **PATCH** (0.0.1): Bug fixes, backward compatible

### Version Workflow

```bash
# Update version in pyproject.toml or use setuptools-scm
git tag v1.0.0
git push origin v1.0.0

# setuptools-scm will automatically use the tag
python -m build
```

---

## 📊 Post-Publication Tasks

### 1. **Update Documentation**

- [ ] Update installation instructions in README.md
- [ ] Update integration guide
- [ ] Update client configuration examples
- [ ] Remove "development status" notices

### 2. **Add PyPI Badge**

```markdown
[![PyPI version](https://badge.fury.io/py/finos-ai-governance-mcp-server.svg)](https://badge.fury.io/py/finos-ai-governance-mcp-server)
[![Downloads](https://pepy.tech/badge/finos-ai-governance-mcp-server)](https://pepy.tech/project/finos-ai-governance-mcp-server)
```

### 3. **Announce Release**

- [ ] Create GitHub release with changelog
- [ ] Update FINOS community
- [ ] Share on relevant forums/communities
- [ ] Update documentation sites

---

## 🔒 Security Considerations

### Package Security

- Never include secrets in published package
- Use secure authentication for PyPI uploads
- Enable 2FA on PyPI account
- Monitor package for vulnerabilities

### API Tokens

Store PyPI API token securely:

```bash
# Create ~/.pypirc
[pypi]
username = __token__
password = pypi-your-api-token-here

[testpypi]
username = __token__
password = pypi-your-test-api-token-here
```

---

## 📈 Monitoring

After publication, monitor:

- Download statistics
- User feedback and issues
- Security vulnerabilities
- Dependency updates

---

## 🔄 Maintenance Releases

For ongoing maintenance:

```bash
# Fix bugs, update dependencies
git commit -m "fix: resolve security vulnerability in dependency"

# Tag new version
git tag v1.0.1

# Build and publish
python -m build
python -m twine upload dist/*
```

---

*This guide will be used when the package is ready for public release.*
