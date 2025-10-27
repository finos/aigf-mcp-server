# Static Fallback Maintenance Guide

## Overview

The FINOS MCP server uses static fallback lists to provide basic functionality when the GitHub API is unavailable (rate-limited, network issues, etc.). These lists must stay synchronized with the actual GitHub repository to prevent ID mapping bugs.

## The Problem

**Symptoms of outdated static fallback:**
- ✅ `list_risks()` returns risk IDs
- ✅ `search_risks()` finds risks
- ❌ `get_risk(id)` fails with "not found"

**Root cause:** Static fallback lists contain outdated filenames that no longer exist in the GitHub repository.

## Solution

### Automated Update Process

**1. Run the update script:**
```bash
python scripts/update-static-fallback.py
```

This script:
- Fetches current file lists from GitHub API
- Generates updated Python code
- Saves to `static_fallback_lists.py`
- Shows what needs to be updated

**2. Review the changes:**
```bash
cat static_fallback_lists.py
```

Check that:
- File counts are reasonable (23 risks, 23 mitigations, 7 frameworks)
- Filenames follow the pattern: `ri-N_description.md`, `mi-N_description.md`, `framework.yml`
- No suspicious or malicious filenames

**3. Apply the update:**

The script already updated `src/finos_mcp/content/discovery.py` lines 26-89.

**4. Verify the fix:**
```bash
# Run integration test
pytest tests/integration/test_static_fallback_sync.py -v

# Or run ID mapping test
python tests/test_id_mapping.py
```

**5. Commit the changes:**
```bash
git add src/finos_mcp/content/discovery.py
git commit -m "fix(discovery): update static fallback lists to match GitHub repository

- Updated STATIC_MITIGATION_FILES (17 → 23 files)
- Updated STATIC_RISK_FILES (17 → 23 files)
- Updated STATIC_FRAMEWORK_FILES (5 → 7 files)
- Fixes ID mapping mismatch between list/search and get operations

Generated with: python scripts/update-static-fallback.py"
```

## When to Update

### Required Updates

1. **Before releases** - Always verify sync before releasing
2. **When tests fail** - If `test_static_fallback_sync.py` fails in CI
3. **After upstream changes** - When FINOS repository adds/removes files

### Scheduled Updates

Run monthly or when notified of upstream changes:
```bash
# Set up a reminder or cron job
# Monthly update check
0 0 1 * * cd /path/to/IA-FINOS && python scripts/update-static-fallback.py
```

## Continuous Integration

The CI pipeline includes automated validation:

```yaml
# .github/workflows/test.yml
- name: Verify static fallback sync
  run: pytest tests/integration/test_static_fallback_sync.py -v
```

**If this test fails in CI:**
1. Someone added/removed files in the FINOS repository
2. Follow the update process above
3. Push the fix

## Manual Verification

**Check if update is needed:**
```bash
# Compare counts
python -c "
from finos_mcp.content.discovery import STATIC_RISK_FILES, STATIC_MITIGATION_FILES
print(f'Static risks: {len(STATIC_RISK_FILES)}')
print(f'Static mitigations: {len(STATIC_MITIGATION_FILES)}')
"

# Then check GitHub
# Visit: https://github.com/finos/ai-governance-framework/tree/main/docs/_risks
# Count the files and compare
```

**Test ID mapping manually:**
```bash
python tests/test_id_mapping.py
```

Expected output:
```
Risk ID mapping: ✓ PASS
Mitigation ID mapping: ✓ PASS
```

## Technical Details

### File Locations

- **Static lists:** `src/finos_mcp/content/discovery.py` lines 26-89
- **Update script:** `scripts/update-static-fallback.py`
- **Validation test:** `tests/integration/test_static_fallback_sync.py`
- **ID mapping test:** `tests/test_id_mapping.py`

### ID Extraction Logic

The system strips prefixes to create IDs:
- `ri-10_prompt-injection.md` → ID: `10_prompt-injection`
- `mi-1_ai-data-leakage-prevention-and-detection.md` → ID: `1_ai-data-leakage-prevention-and-detection`
- `nist-ai-600-1.yml` → ID: `nist-ai-600-1`

**Critical:** Static fallback filenames MUST match GitHub repository filenames exactly.

### Fallback Activation

Static fallback is used when:
- GitHub API returns 403 (rate limited)
- GitHub API returns 5xx (server error)
- Network connectivity issues
- `FINOS_MCP_GITHUB_TOKEN` not set and 60/hour limit exceeded

## Troubleshooting

### "Failed to fetch files from GitHub API"

**Cause:** Rate limit exceeded or network issues

**Solutions:**
1. Wait 1 hour for rate limit reset
2. Add GitHub token: `export FINOS_MCP_GITHUB_TOKEN="your_token"`
3. Check network connectivity

### "Using cache instead of github_api"

**Cause:** Recently fetched, cache still valid

**Solution:**
```bash
# Clear cache and retry
rm -rf .cache/discovery
python scripts/update-static-fallback.py
```

### Test fails with "Missing from static"

**Cause:** GitHub repository added new files

**Solution:** Run update script and commit changes

### Test fails with "Extra in static"

**Cause:** GitHub repository removed files

**Solution:** Run update script and commit changes

## Best Practices

1. ✅ **Always run update script** - Don't manually edit the lists
2. ✅ **Review before committing** - Verify counts and filenames make sense
3. ✅ **Run tests after update** - Ensure ID mapping works
4. ✅ **Include in release checklist** - Verify sync before every release
5. ✅ **Monitor CI failures** - React quickly to sync test failures
6. ❌ **Never skip validation** - Always run the integration test

## Prevention Strategy

### Code-Level Prevention

The static fallback lists now include:
```python
# Static fallback lists (auto-generated - do not edit manually)
# To update: python scripts/update-static-fallback.py
# Last updated: 2025-10-27
```

This discourages manual editing and provides update instructions.

### Test-Level Prevention

Integration test `test_static_fallback_sync.py` runs in CI and:
- Compares static lists with GitHub API
- Reports missing/extra files
- Fails CI if out of sync
- Provides clear remediation steps

### Process-Level Prevention

1. **Monthly sync checks** - Scheduled validation
2. **Pre-release verification** - Required step before releases
3. **Documentation** - This guide ensures team awareness
4. **Automation** - Update script eliminates manual errors

## Emergency Fix

If production is broken due to outdated fallback:

```bash
# 1. Quick fix (5 minutes)
python scripts/update-static-fallback.py
git add src/finos_mcp/content/discovery.py
git commit -m "fix(discovery): emergency update of static fallback lists"
git push

# 2. Verify fix
pytest tests/test_id_mapping.py

# 3. Deploy
# (follow your deployment process)
```

## Related Files

- `src/finos_mcp/content/discovery.py` - Contains static fallback lists
- `scripts/update-static-fallback.py` - Update script
- `tests/integration/test_static_fallback_sync.py` - Validation test
- `tests/test_id_mapping.py` - ID flow verification test
- `docs/static-fallback-maintenance.md` - This guide

## Questions?

- Review test failures in CI
- Check `test_id_mapping.py` output for debugging
- Examine `discovery.py` comments for context
