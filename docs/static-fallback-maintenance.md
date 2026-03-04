# Discovery Unavailability Behavior

## Overview

The server now uses **live discovery only** for risks, mitigations, and frameworks.
When the upstream repository is unavailable, tools return explicit unavailability
signals instead of static filename fallback catalogs.

## Why this changed

Static filename catalogs can drift from upstream and create misleading behavior.
The new design prioritizes explicit failure signals over stale data.

## Runtime behavior

1. Discovery success:
- `source`: `github_api` or `cache`
- Tools return normal data.

2. Discovery unavailable:
- `source`: `unavailable`
- List/search tools return empty results plus a message.
- Get tools return a user-facing unavailable message in `content`.

## Operational response

1. Check upstream connectivity to GitHub API/raw content.
2. Validate token/rate-limit status (`FINOS_MCP_GITHUB_TOKEN`).
3. Retry once connectivity is restored.

## Validation

Run integration checks:

```bash
pytest tests/integration/test_static_fallback_sync.py -v
```

This verifies that unavailability is explicit and static fallback catalogs are not used.
