# CI Configuration Analysis Report

## Critical Configuration Discrepancies Found

### MyPy Command Differences

**GitHub Actions CI (security-analysis.yml:149-156)**:
```bash
python -m mypy src/finos_mcp \
  --show-error-codes \
  --show-error-context \
  --txt-report security-reports/mypy-report \
  --strict-optional \
  --warn-redundant-casts \
  --warn-unused-ignores
```

**Local ci-local.sh (line 36)**:
```bash
mypy src/ --show-error-codes
```

**Pre-commit (.pre-commit-config.yaml:20)**:
```bash
args: [--show-error-codes, --show-error-context, --strict-optional, --warn-redundant-casts, --warn-unused-ignores]
files: ^src/.*\.py$
exclude: ^src/finos_mcp/internal/.*\.py$
```

**Quality-check.sh (line 178)**:
```bash
mypy src/finos_mcp --show-error-codes --show-error-context --strict-optional --warn-redundant-casts --warn-unused-ignores
```

### Configuration File Conflicts

**1. .mypy.ini vs pyproject.toml**

`.mypy.ini`:
- python_version = 3.10
- no_strict_optional = True (CONFLICTS with CI --strict-optional)
- exclude = (src/finos_mcp/internal/.*\.py|tests/internal/.*\.py|scripts/.*\.py)

`pyproject.toml [tool.mypy]`:
- python_version = "3.10"
- strict = true
- exclude = ["src/finos_mcp/internal/", "tests/integration/test_live_mcp_server.py"]

**2. Path Target Differences**
- CI targets: `src/finos_mcp` (specific module)
- Local scripts: `src/` (entire src directory)
- Pre-commit: `^src/.*\.py$` (all Python files in src/)

### Root Cause Analysis

1. **Configuration Precedence Issue**: MyPy reads both .mypy.ini AND pyproject.toml, with conflicting settings
2. **Path Scope Mismatch**: CI only checks `src/finos_mcp` while local tools check broader scopes
3. **Flag Inconsistency**: Local ci-local.sh missing critical flags that CI uses
4. **Exclusion Conflicts**: Different exclude patterns between config files

### Impact

This configuration drift means:
- Local validation passes but CI fails
- MyPy checks different file sets locally vs CI
- Conflicting strict settings mask type errors locally
- Pre-commit hooks don't catch what CI catches

### Solution Required

1. Eliminate .mypy.ini completely (use only pyproject.toml)
2. Align all MyPy commands to match CI exactly
3. Create exact CI simulation script
4. Update pre-commit to use identical CI commands
