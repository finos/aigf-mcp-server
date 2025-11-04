# Documentation Synchronization Issues Found

## Summary

During code review, found that public documentation was **out of sync** with actual codebase implementation.

## Issues Fixed

### 1. ✅ README.md - Tool Name Correction
- **File**: `README.md`
- **Issue**: Used incorrect tool name `get_framework_content`
- **Actual Tool**: `get_framework`
- **Status**: FIXED (2 occurrences corrected)

### 2. ✅ docs/api/README.md - Tool Count Correction
- **File**: `docs/api/README.md`
- **Issue**: Stated "21 MCP tools" instead of actual 11 tools
- **Status**: FIXED

### 3. ✅ docs/api/README.md - Non-Existent Tools Removed
- **File**: `docs/api/README.md`
- **Issue**: Documentation referenced tools that don't exist in codebase:
  - `get_framework_details` (actual: `get_framework`)
  - `get_compliance_analysis` (doesn't exist)
  - `export_framework_data` (doesn't exist)
  - `find_compliance_gaps` (doesn't exist)
- **Status**: FIXED - replaced with actual 11 tools

### 4. ✅ docs/api/README.md - Tool Categories Corrected
- **File**: `docs/api/README.md`
- **Issue**: Incorrect categorization (11 + 4 + 4 = 19 tools)
- **Actual**: 5 + 4 + 2 = 11 tools
- **Status**: FIXED

## Issues Requiring Attention (OUT OF SCOPE FOR THIS SESSION)

### 5. ⚠️  docs/user-guide/ - Multiple Files with Non-Existent Tools

The following files contain references to non-existent tools and need to be rewritten or removed:

- `docs/user-guide/compliance-analysis.md` - References `get_compliance_analysis`
- `docs/user-guide/cross-framework-navigation.md` - References `find_compliance_gaps`
- `docs/user-guide/export-reporting.md` - References `export_framework_data`
- `docs/user-guide/framework-search.md` - References multiple non-existent tools
- `docs/user-guide/getting-started.md` - References non-existent tools

**Recommendation**: These files appear to be from an earlier design that included compliance analysis and export tools that were never implemented. Options:

1. **Remove these files** entirely (cleanest approach per KISS principles)
2. **Rewrite** them to use only the 11 actual tools
3. **Add disclaimer** that these are "planned features" (not recommended - violates single source of truth principle)

## Actual MCP Tools (11 Total)

### Framework Access Tools (5)
1. `list_frameworks`
2. `get_framework`
3. `search_frameworks`
4. `list_risks`
5. `get_risk`

### Risk & Mitigation Tools (4)
6. `search_risks`
7. `list_mitigations`
8. `get_mitigation`
9. `search_mitigations`

### System Monitoring Tools (2)
10. `get_service_health`
11. `get_cache_stats`

## Verification Command

To verify tool count matches documentation:
```bash
grep "@mcp.tool()" src/finos_mcp/fastmcp_server.py | wc -l
# Should output: 11
```

## Next Steps

1. ✅ Commit README.md and docs/api/README.md fixes
2. ⚠️  Decide on docs/user-guide/ files (remove vs rewrite)
3. ✅ Update PR description if needed
4. ✅ Ensure CI passes with documentation changes

## CLAUDE.md Principle Violated

**"Update After Changes: Docs synchronized with code always"**

The documentation was not updated when the architecture was simplified from 21 planned tools to 11 actual tools. This created confusion between documented vs. actual capabilities.

## Prevention

- Add documentation validation to pre-commit hooks
- Create script to cross-reference documented tools with actual `@mcp.tool()` decorators
- Add to quality-check.sh: Tool count validation
